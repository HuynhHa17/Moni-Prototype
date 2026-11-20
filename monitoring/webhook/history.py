import argparse
import csv
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

VN = timezone(timedelta(hours=7), "UTC+7")  # Việt Nam không đổi giờ theo mùa

EPISODE_COLS = ["id", "alertname", "host", "service", "severity", "status",
                "starts_at", "ends_at", "missing_firing",
                "first_received_at", "last_received_at"]
EVENT_COLS = ["id", "episode_id", "status", "outcome", "ends_at", "received_at", "group_key"]


def open_readonly(path):
    """Mở CSDL ở chế độ chỉ đọc: không tạo file mới, không ghi được gì."""
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def to_local(value):
    """Đổi chuỗi UTC trong CSDL sang giờ Việt Nam để hiển thị."""
    if not value:
        return "-"
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.astimezone(VN).strftime("%Y-%m-%d %H:%M:%S")


def duration(starts_at, ends_at):
    """Thời gian sự cố; chưa có ends_at thì không tự tính."""
    if not ends_at:
        return "-"
    start = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
    end = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
    return str(end - start).split(".")[0]


def query_episodes(conn, host=None, status=None, limit=None):
    sql = f"SELECT {', '.join(EPISODE_COLS)} FROM episodes WHERE 1 = 1"
    params = []
    if host:
        sql += " AND host = ?"
        params.append(host)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY starts_at DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return conn.execute(sql, params).fetchall()


def query_events(conn, episode_id=None):
    sql = f"SELECT {', '.join(EVENT_COLS)} FROM events"
    params = []
    if episode_id is not None:
        sql += " WHERE episode_id = ?"
        params.append(episode_id)
    return conn.execute(sql + " ORDER BY id", params).fetchall()


def print_table(header, rows, out):
    widths = [max(len(str(h)), *(len(str(r[i])) for r in rows)) for i, h in enumerate(header)]
    line = "  ".join(str(h).ljust(w) for h, w in zip(header, widths))
    out.write(line + "\n" + "-" * len(line) + "\n")
    for r in rows:
        out.write("  ".join(str(v).ljust(w) for v, w in zip(r, widths)) + "\n")


def cmd_episodes(conn, args, out):
    rows = query_episodes(conn, args.host, args.status, args.limit)
    header = ["id", "alertname", "host", "status", "bắt đầu (UTC+7)",
              "kết thúc (UTC+7)", "thời gian", "thiếu firing"]
    view = [(r[0], r[1], r[2] or "-", r[5], to_local(r[6]), to_local(r[7]),
             duration(r[6], r[7]), "có" if r[8] else "") for r in rows]
    print_table(header, view, out)
    out.write(f"{len(rows)} episode\n")


def cmd_events(conn, args, out):
    rows = query_events(conn, args.episode_id)
    header = ["id", "episode", "status", "outcome", "nhận lúc (UTC+7)"]
    view = [(r[0], r[1], r[2], r[3], to_local(r[5])) for r in rows]
    print_table(header, view, out)
    out.write(f"{len(rows)} sự kiện\n")


def cmd_export(conn, args, out):
    if args.table == "episodes":
        header, rows = EPISODE_COLS, query_episodes(conn, args.host, args.status)
    else:
        header, rows = EVENT_COLS, query_events(conn)
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerows(rows)  # giữ nguyên giá trị UTC để đối chiếu với payload


def build_parser():
    p = argparse.ArgumentParser(description="Xem và xuất lịch sử cảnh báo (chỉ đọc).")
    p.add_argument("--db", default="history.db", help="đường dẫn CSDL SQLite")
    sub = p.add_subparsers(dest="command", required=True)

    ep = sub.add_parser("episodes", help="liệt kê các lần phát sinh cảnh báo")
    ep.add_argument("--host")
    ep.add_argument("--status", choices=["firing", "resolved"])
    ep.add_argument("--limit", type=int)

    ev = sub.add_parser("events", help="liệt kê thư firing/resolved đã nhận")
    ev.add_argument("--episode-id", type=int)

    ex = sub.add_parser("export", help="xuất CSV ra màn hình hoặc file")
    ex.add_argument("table", choices=["episodes", "events"])
    ex.add_argument("--host")
    ex.add_argument("--status", choices=["firing", "resolved"])
    ex.add_argument("--output", help="file CSV; bỏ trống thì in ra màn hình")
    return p


def main(argv=None, out=None):
    args = build_parser().parse_args(argv)
    out = out or sys.stdout
    try:
        conn = open_readonly(args.db)
        conn.execute("SELECT 1 FROM episodes LIMIT 1")
    except sqlite3.Error as exc:
        sys.stderr.write(f"không mở được CSDL {args.db}: {exc}\n")
        return 1
    try:
        if args.command == "export" and args.output:
            with open(args.output, "w", newline="", encoding="utf-8") as f:
                cmd_export(conn, args, f)
            out.write(f"đã xuất {args.table} ra {args.output}\n")
        else:
            {"episodes": cmd_episodes, "events": cmd_events, "export": cmd_export}[args.command](conn, args, out)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
