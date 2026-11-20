import json
import logging
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import store

ZERO_TIME = "0001-01-01T00:00:00Z"
VALID_STATUS = ("firing", "resolved")
MAX_BODY = 1024 * 1024  # 1 MiB, đủ cho một notification

log = logging.getLogger("webhook")


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


def parse_payload(body):
    """Đọc body JSON, trả về (group_key, danh sách alert đã chuẩn hóa)."""
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

    # Trạng thái lấy từ TỪNG alert, không lấy data["status"] của cả nhóm.
    normalized = [normalize_alert(a, i) for i, a in enumerate(alerts)]
    return data.get("groupKey"), normalized


class Handler(BaseHTTPRequestHandler):
    server_version = "moni-webhook"

    def _reply(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/alerts":
            self._reply(404, {"error": "không có đường dẫn này"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self._reply(400, {"error": "Content-Length thiếu hoặc quá lớn"})
            return

        try:
            group_key, alerts = parse_payload(self.rfile.read(length))
        except PayloadError as exc:
            log.warning("từ chối payload: %s", exc)
            self._reply(400, {"error": str(exc)})
            return

        try:
            conn = store.connect(self.server.db_path)
            try:
                outcomes = store.record_alerts(conn, group_key, alerts)
            finally:
                conn.close()
        except sqlite3.Error as exc:
            log.error("không ghi được CSDL: %s", exc)
            self._reply(500, {"error": "không ghi được CSDL"})
            return

        for a, outcome in zip(alerts, outcomes):
            log.info(
                "lưu alert outcome=%s status=%s alertname=%s host=%s fingerprint=%s startsAt=%s endsAt=%s",
                outcome, a["status"], a["alertname"], a["host"], a["fingerprint"],
                a["starts_at"], a["ends_at"],
            )
        self._reply(200, {"accepted": len(alerts), "outcomes": outcomes})

    def log_message(self, fmt, *args):
        log.debug("%s - %s", self.address_string(), fmt % args)


def main():
    logging.basicConfig(
        level=os.environ.get("WEBHOOK_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    port = int(os.environ.get("WEBHOOK_PORT", "8080"))
    db_path = os.environ.get("WEBHOOK_DB", "history.db")
    store.connect(db_path).close()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.db_path = db_path
    log.info("webhook lắng nghe cổng %s, đường dẫn POST /alerts, CSDL %s", port, db_path)
    server.serve_forever()


if __name__ == "__main__":
    main()
