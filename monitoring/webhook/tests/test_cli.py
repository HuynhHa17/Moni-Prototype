import copy
import csv
import hashlib
import io
import pathlib
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import history  # noqa: E402
import store  # noqa: E402
from app import parse_payload  # noqa: E402

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def digest(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(pathlib.Path(self.tmp.name) / "history.db")
        gk, firing = parse_payload((FIXTURES / "firing.json").read_bytes())
        _, resolved = parse_payload((FIXTURES / "resolved.json").read_bytes())
        again = copy.deepcopy(firing[0])
        again["starts_at"] = "2026-11-13T12:10:15.534Z"
        conn = store.connect(self.db)
        store.record_alerts(conn, gk, firing, "2026-11-13T11:17:30.000Z")
        store.record_alerts(conn, gk, firing, "2026-11-13T11:33:30.000Z")
        store.record_alerts(conn, gk, resolved, "2026-11-13T11:45:30.000Z")
        store.record_alerts(conn, gk, [again], "2026-11-13T12:10:45.000Z")
        conn.close()

    def run_cli(self, *args):
        out = io.StringIO()
        code = history.main(["--db", self.db, *args], out)
        return code, out.getvalue()

    def test_episodes_view(self):
        code, text = self.run_cli("episodes")
        self.assertEqual(code, 0)
        self.assertIn("2026-11-13 18:17:00", text)  # 11:17:00 UTC hiển thị giờ Việt Nam
        self.assertIn("0:28:00", text)  # 11:17:00 → 11:45:00
        self.assertIn("2 episode", text)

    def test_filter_status(self):
        _, text = self.run_cli("episodes", "--status", "firing")
        self.assertIn("1 episode", text)

    def test_events_view(self):
        _, text = self.run_cli("events", "--episode-id", "1")
        self.assertIn("repeat", text)
        self.assertIn("3 sự kiện", text)

    def test_export_csv_keeps_utc(self):
        _, text = self.run_cli("export", "episodes")
        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertEqual(len(rows), 2)
        old = [r for r in rows if r["status"] == "resolved"][0]
        self.assertEqual(old["starts_at"], "2026-11-13T11:17:00.534Z")
        self.assertEqual(old["ends_at"], "2026-11-13T11:45:00.534Z")
        new = [r for r in rows if r["status"] == "firing"][0]
        self.assertEqual(new["ends_at"], "")  # không tự tạo giờ kết thúc

    def test_export_events_to_file(self):
        target = pathlib.Path(self.tmp.name) / "events.csv"
        code, _ = self.run_cli("export", "events", "--output", str(target))
        self.assertEqual(code, 0)
        with target.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([r["outcome"] for r in rows], ["new", "repeat", "resolve", "new"])

    def test_queries_do_not_change_db(self):
        before = digest(self.db)
        self.run_cli("episodes")
        self.run_cli("events")
        self.run_cli("export", "episodes")
        self.assertEqual(digest(self.db), before)

    def test_readonly_connection_rejects_write(self):
        conn = history.open_readonly(self.db)
        with self.assertRaises(sqlite3.OperationalError):
            conn.execute("DELETE FROM events")
        conn.close()

    def test_missing_db_is_not_created(self):
        missing = pathlib.Path(self.tmp.name) / "khong-co.db"
        code = history.main(["--db", str(missing), "episodes"], io.StringIO())
        self.assertEqual(code, 1)
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
