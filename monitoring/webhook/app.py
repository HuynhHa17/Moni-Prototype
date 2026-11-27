import json
import logging
import os
import signal
import sqlite3
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import store

ZERO_TIME = "0001-01-01T00:00:00Z"
VALID_STATUS = ("firing", "resolved")
MAX_BODY = 1024 * 1024  # 1 MiB, đủ cho một notification

HEALTH_SCOPE = "tiến trình webhook chạy và CSDL mở được, lấy được khóa ghi; không kiểm tra Alertmanager hay Prometheus"

log = logging.getLogger("webhook")


class Metrics:
    """Bộ đếm Prometheus nội bộ cho tiến trình webhook."""

    def __init__(self):
        self._lock = threading.Lock()
        self.requests = Counter()
        self.alerts = Counter()
        self.db_errors = 0
        self.truncated_alerts = 0

    def inc_request(self, path: str, code: int) -> None:
        with self._lock:
            self.requests[(path, str(code))] += 1

    def inc_outcomes(self, outcomes) -> None:
        with self._lock:
            for outcome in outcomes:
                self.alerts[outcome] += 1

    def inc_db_error(self) -> None:
        with self._lock:
            self.db_errors += 1

    def inc_truncated(self, count: int) -> None:
        if count > 0:
            with self._lock:
                self.truncated_alerts += count

    def render(self) -> str:
        lines = [
            "# HELP moni_webhook_requests_total Total HTTP requests handled by moni-webhook.",
            "# TYPE moni_webhook_requests_total counter",
        ]
        with self._lock:
            for (path, code), value in sorted(self.requests.items()):
                lines.append(f'moni_webhook_requests_total{{path="{path}",code="{code}"}} {value}')
            lines.extend([
                "# HELP moni_webhook_alerts_total Total alerts recorded by outcome.",
                "# TYPE moni_webhook_alerts_total counter",
            ])
            for outcome, value in sorted(self.alerts.items()):
                lines.append(f'moni_webhook_alerts_total{{outcome="{outcome}"}} {value}')
            lines.extend([
                "# HELP moni_webhook_db_errors_total Total database errors encountered by moni-webhook.",
                "# TYPE moni_webhook_db_errors_total counter",
                f"moni_webhook_db_errors_total {self.db_errors}",
                "# HELP moni_webhook_truncated_alerts_total Total alerts truncated by Alertmanager payloads.",
                "# TYPE moni_webhook_truncated_alerts_total counter",
                f"moni_webhook_truncated_alerts_total {self.truncated_alerts}",
            ])
        return "\n".join(lines) + "\n"


METRICS = Metrics()


class PayloadError(ValueError):
    """Payload không đúng định dạng webhook v4 của Alertmanager."""


def normalize_alert(alert, index):
    """Kiểm tra một phần tử của alerts[] và trả về bản đã chuẩn hóa."""
    where = f"alerts[{index}]"
    if not isinstance(alert, dict):
        raise PayloadError(f"{where} phải là object")

    status = alert.get("status")
    if status not in VALID_STATUS:
        raise PayloadError(f"{where}.status phải là firing hoặc resolved")

    fingerprint = alert.get("fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint:
        raise PayloadError(f"{where}.fingerprint thiếu hoặc rỗng")

    starts_at = alert.get("startsAt")
    if not isinstance(starts_at, str) or not starts_at or starts_at == ZERO_TIME:
        raise PayloadError(f"{where}.startsAt thiếu hoặc không hợp lệ")

    labels = alert.get("labels")
    if not isinstance(labels, dict) or not labels.get("alertname"):
        raise PayloadError(f"{where}.labels phải có alertname")

    annotations = alert.get("annotations") or {}
    if not isinstance(annotations, dict):
        raise PayloadError(f"{where}.annotations phải là object")

    ends_at = alert.get("endsAt")
    if ends_at in (None, "", ZERO_TIME):
        ends_at = None  # chưa có giờ kết thúc, không tự tạo

    return {
        "status": status,
        "fingerprint": fingerprint,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "alertname": labels["alertname"],
        "host": labels.get("host"),
        "service": labels.get("service"),
        "severity": labels.get("severity"),
        "labels": labels,
        "annotations": annotations,
    }


def parse_payload_with_meta(body):
    """Đọc body JSON, trả về (group_key, danh sách alert đã chuẩn hóa, truncated_alerts)."""
    try:
        data = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PayloadError(f"body không phải JSON: {exc}") from None

    if not isinstance(data, dict):
        raise PayloadError("body phải là object JSON")
    if data.get("version") != "4":
        raise PayloadError("chỉ hỗ trợ webhook version 4")

    alerts = data.get("alerts")
    if not isinstance(alerts, list) or not alerts:
        raise PayloadError("alerts phải là danh sách không rỗng")

    truncated = data.get("truncatedAlerts") or 0
    if not isinstance(truncated, int) or truncated < 0:
        truncated = 0

    # Trạng thái lấy từ TỪNG alert, không lấy data["status"] của cả nhóm.
    normalized = [normalize_alert(a, i) for i, a in enumerate(alerts)]
    return data.get("groupKey"), normalized, truncated


def parse_payload(body):
    """Đọc body JSON, trả về (group_key, danh sách alert đã chuẩn hóa)."""
    group_key, normalized, _ = parse_payload_with_meta(body)
    return group_key, normalized


class Handler(BaseHTTPRequestHandler):
    server_version = "moni-webhook"

    def _metrics(self) -> Metrics:
        return getattr(self.server, "metrics", METRICS)

    def _reply(self, code, payload, path_label=None):
        self._metrics().inc_request(path_label or self.path, code)
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/metrics":
            body = self._metrics().render().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path != "/health":
            self._reply(404, {"error": "không có đường dẫn này"})
            return

        try:
            store.check(self.server.db_path)
        except (sqlite3.Error, store.StoreError) as exc:
            self._metrics().inc_db_error()
            log.error("health: CSDL lỗi: %s", exc)
            self._reply(503, {"status": "error", "db": "không mở hoặc không ghi được", "scope": HEALTH_SCOPE})
            return
        self._reply(200, {"status": "ok", "db": "ok", "scope": HEALTH_SCOPE})

    def do_POST(self):
        if self.path != "/alerts":
            self._reply(404, {"error": "không có đường dẫn này"})
            return

        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length) if raw_length is not None else 0
        except ValueError:
            self._reply(400, {"error": "Content-Length không hợp lệ"})
            return
        if length <= 0 or length > MAX_BODY:
            self._reply(400, {"error": "Content-Length thiếu hoặc quá lớn"})
            return

        try:
            group_key, alerts, truncated = parse_payload_with_meta(self.rfile.read(length))
        except PayloadError as exc:
            log.warning("từ chối payload: %s", exc)
            self._reply(400, {"error": str(exc)})
            return

        if truncated > 0:
            self._metrics().inc_truncated(truncated)
            log.warning("Alertmanager cắt bớt %d alert trong notification groupKey=%s", truncated, group_key)

        try:
            conn = store.connect(self.server.db_path)
            try:
                outcomes = store.record_alerts(conn, group_key, alerts)
            finally:
                conn.close()
        except Exception as exc:
            self._metrics().inc_db_error()
            log.error("không ghi được CSDL: %s", exc)
            self._reply(500, {"error": "không ghi được CSDL"})
            return

        self._metrics().inc_outcomes(outcomes)
        for a, outcome in zip(alerts, outcomes):
            log.info(
                "lưu alert outcome=%s status=%s alertname=%s host=%s fingerprint=%s startsAt=%s endsAt=%s",
                outcome, a["status"], a["alertname"], a["host"], a["fingerprint"],
                a["starts_at"], a["ends_at"],
            )
        self._reply(200, {"accepted": len(alerts), "outcomes": outcomes})

    def log_message(self, fmt, *args):
        log.debug("%s - %s", self.address_string(), fmt % args)


def _target_label(db_target: str) -> str:
    if store.is_postgres(db_target):
        return "postgresql://<configured>"
    return db_target


def main():
    logging.basicConfig(
        level=os.environ.get("WEBHOOK_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    port = int(os.environ.get("WEBHOOK_PORT", "8080"))
    db_target = os.environ.get("WEBHOOK_DSN") or os.environ.get("WEBHOOK_DB", "history.db")
    store.init_db(db_target)

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.db_path = db_target
    server.metrics = METRICS

    def _handle_signal(signum, _frame):
        log.info("nhận tín hiệu %s, đang dừng webhook an toàn...", signum)
        threading.Thread(target=server.shutdown, daemon=True).start()

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _handle_signal)

    log.info("webhook lắng nghe cổng %s, đường dẫn POST /alerts, GET /health, GET /metrics, CSDL %s",
             port, _target_label(db_target))
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
