import json
import pathlib
import sqlite3
from datetime import datetime, timezone

SCHEMA = pathlib.Path(__file__).with_name("schema.sql")


def utc_now():
    """Giờ hiện tại dạng ISO 8601 UTC, cùng kiểu với startsAt trong payload."""
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    return now.replace("+00:00", "Z")


def connect(path):
    """Mở CSDL, bật khóa ngoại và tạo bảng nếu chưa có."""
    conn = sqlite3.connect(path, timeout=5, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


def _record_one(conn, alert, group_key, received_at):
    """Ghi một alert theo bảng quy tắc mục 5.3, trả về outcome."""
    row = conn.execute(
        "SELECT id, status FROM episodes WHERE fingerprint = ? AND starts_at = ?",
        (alert["fingerprint"], alert["starts_at"]),
    ).fetchone()

    if row is None:
        missing_firing = 1 if alert["status"] == "resolved" else 0
        cur = conn.execute(
            """INSERT INTO episodes (fingerprint, starts_at, alertname, host, service,
                   severity, labels_json, annotations_json, status, ends_at,
                   missing_firing, first_received_at, last_received_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                alert["fingerprint"], alert["starts_at"], alert["alertname"],
                alert["host"], alert["service"], alert["severity"],
                json.dumps(alert["labels"], ensure_ascii=False, sort_keys=True),
                json.dumps(alert["annotations"], ensure_ascii=False, sort_keys=True),
                alert["status"],
                alert["ends_at"] if alert["status"] == "resolved" else None,
                missing_firing, received_at, received_at,
            ),
        )
        episode_id = cur.lastrowid
        outcome = "resolved_without_firing" if missing_firing else "new"
    else:
        episode_id, current = row
        if alert["status"] == "firing":
            outcome = "repeat" if current == "firing" else "late_firing"
        elif current == "firing":
            outcome = "resolve"
            conn.execute(
                "UPDATE episodes SET status = 'resolved', ends_at = ? WHERE id = ?",
                (alert["ends_at"], episode_id),
            )
        else:
            outcome = "resolved_repeat"
        conn.execute(
            "UPDATE episodes SET last_received_at = ? WHERE id = ?",
            (received_at, episode_id),
        )

    conn.execute(
        """INSERT INTO events (episode_id, status, ends_at, received_at, group_key, outcome)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (episode_id, alert["status"], alert["ends_at"], received_at, group_key, outcome),
    )
    return outcome


def record_alerts(conn, group_key, alerts, received_at=None):
    """Ghi mọi alert của một notification trong MỘT giao dịch: ghi hết hoặc không ghi gì."""
    received_at = received_at or utc_now()
    conn.execute("BEGIN IMMEDIATE")
    try:
        outcomes = [_record_one(conn, a, group_key, received_at) for a in alerts]
    except Exception:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
    return outcomes
