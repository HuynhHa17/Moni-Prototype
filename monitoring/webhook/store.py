import json
import pathlib
import sqlite3
import threading
from datetime import datetime, timezone

try:
    import psycopg
except ImportError:  # pragma: no cover - local stdlib-only tests use SQLite
    psycopg = None

SCHEMA_SQLITE = pathlib.Path(__file__).with_name("schema.sql")
SCHEMA_PG = pathlib.Path(__file__).with_name("schema_pg.sql")

_INIT_LOCK = threading.Lock()
_INITIALIZED_TARGETS: set[str] = set()


class StoreError(Exception):
    """Lỗi tầng lưu trữ (SQLite hoặc PostgreSQL)."""


def is_postgres(target: str) -> bool:
    return isinstance(target, str) and target.startswith(("postgresql://", "postgres://"))


def utc_now():
    """Giờ hiện tại dạng ISO 8601 UTC, cùng kiểu với startsAt trong payload."""
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    return now.replace("+00:00", "Z")


def _open_sqlite(path: str):
    conn = sqlite3.connect(path, timeout=5, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _open_postgres(dsn: str):
    if psycopg is None:
        raise StoreError("psycopg chưa được cài đặt để kết nối PostgreSQL")
    try:
        return psycopg.connect(dsn, connect_timeout=5, autocommit=False)
    except Exception as exc:
        raise StoreError(f"không kết nối được PostgreSQL: {exc}") from exc


def init_db(target: str) -> None:
    """Khởi tạo schema đúng 1 lần lúc startup (tách khỏi đường đọc/healthcheck)."""
    if is_postgres(target):
        conn = _open_postgres(target)
        try:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_PG.read_text(encoding="utf-8"))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise StoreError(f"không khởi tạo được schema PostgreSQL: {exc}") from exc
        finally:
            conn.close()
        with _INIT_LOCK:
            _INITIALIZED_TARGETS.add(target)
        return

    conn = _open_sqlite(target)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA_SQLITE.read_text(encoding="utf-8"))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            conn.execute("PRAGMA user_version = 1")
    finally:
        conn.close()
    with _INIT_LOCK:
        _INITIALIZED_TARGETS.add(target)


def _ensure_initialized(target: str) -> None:
    with _INIT_LOCK:
        if target in _INITIALIZED_TARGETS:
            return
    init_db(target)


def connect(target: str):
    """Mở kết nối CSDL (tự khởi tạo đúng 1 lần nếu chưa chạy init_db)."""
    if is_postgres(target):
        _ensure_initialized(target)
        return _open_postgres(target)
    _ensure_initialized(target)
    return _open_sqlite(target)


def check(target: str) -> None:
    """Kiểm tra mở được CSDL và sẵn sàng ghi; không chạy DDL hay ghi dữ liệu."""
    if is_postgres(target):
        conn = _open_postgres(target)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            conn.rollback()
        except Exception as exc:
            raise StoreError(f"healthcheck PostgreSQL lỗi: {exc}") from exc
        finally:
            conn.close()
        return

    conn = _open_sqlite(target)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("ROLLBACK")
    finally:
        conn.close()


def _is_pg_conn(conn) -> bool:
    return not isinstance(conn, sqlite3.Connection)


def _record_one_sqlite(conn, alert, group_key, received_at):
    """Ghi một alert vào SQLite theo quy tắc episode/event, trả về outcome."""
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


def _record_one_pg(cur, alert, group_key, received_at):
    """Ghi một alert vào PostgreSQL 16 với khóa hàng FOR UPDATE, trả về outcome."""
    cur.execute(
        "SELECT id, status FROM episodes WHERE fingerprint = %s AND starts_at = %s FOR UPDATE",
        (alert["fingerprint"], alert["starts_at"]),
    )
    row = cur.fetchone()

    if row is None:
        missing_firing = 1 if alert["status"] == "resolved" else 0
        cur.execute(
            """INSERT INTO episodes (fingerprint, starts_at, alertname, host, service,
                   severity, labels_json, annotations_json, status, ends_at,
                   missing_firing, first_received_at, last_received_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s)
               RETURNING id""",
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
        episode_id = cur.fetchone()[0]
        outcome = "resolved_without_firing" if missing_firing else "new"
    else:
        episode_id, current = row
        if alert["status"] == "firing":
            outcome = "repeat" if current == "firing" else "late_firing"
        elif current == "firing":
            outcome = "resolve"
            cur.execute(
                "UPDATE episodes SET status = 'resolved', ends_at = %s WHERE id = %s",
                (alert["ends_at"], episode_id),
            )
        else:
            outcome = "resolved_repeat"
        cur.execute(
            "UPDATE episodes SET last_received_at = %s WHERE id = %s",
            (received_at, episode_id),
        )

    cur.execute(
        """INSERT INTO events (episode_id, status, ends_at, received_at, group_key, outcome)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (episode_id, alert["status"], alert["ends_at"], received_at, group_key, outcome),
    )
    return outcome


def record_alerts(conn, group_key, alerts, received_at=None):
    """Ghi mọi alert của một notification trong MỘT giao dịch: ghi hết hoặc không ghi gì."""
    received_at = received_at or utc_now()
    if _is_pg_conn(conn):
        try:
            with conn.cursor() as cur:
                outcomes = [_record_one_pg(cur, a, group_key, received_at) for a in alerts]
            conn.commit()
            return outcomes
        except Exception:
            conn.rollback()
            raise

    conn.execute("BEGIN IMMEDIATE")
    try:
        outcomes = [_record_one_sqlite(conn, a, group_key, received_at) for a in alerts]
    except Exception:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
    return outcomes
