import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import store  # noqa: E402
from app import parse_payload  # noqa: E402

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def alerts_of(name):
    raw = (FIXTURES / name).read_bytes()
    return parse_payload(raw)


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = store.connect(str(pathlib.Path(self.tmp.name) / "test.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def episodes(self):
        return self.conn.execute(
            "SELECT fingerprint, starts_at, status, ends_at, host, alertname,"
            " first_received_at, last_received_at FROM episodes"
        ).fetchall()

    def events(self):
        return self.conn.execute(
            "SELECT status, ends_at, received_at, outcome FROM events ORDER BY id"
        ).fetchall()

    def test_firing_creates_episode(self):
        gk, alerts = alerts_of("firing.json")
        out = store.record_alerts(self.conn, gk, alerts, "2026-11-13T11:17:30.000Z")
        self.assertEqual(out, ["new"])
        ep = self.episodes()
        self.assertEqual(len(ep), 1)
        fp, starts, status, ends, host, name, first, last = ep[0]
        self.assertEqual((fp, starts, status), ("ffba5f3489ed0334", "2026-11-13T11:17:00.534Z", "firing"))
        self.assertIsNone(ends)  # chưa resolved thì không có giờ kết thúc
        self.assertEqual((host, name), ("workload-vm2", "ServiceHttpDown"))
        self.assertEqual(first, "2026-11-13T11:17:30.000Z")  # giờ nhận tách khỏi startsAt

    def test_resolved_closes_same_episode(self):
        gk, firing = alerts_of("firing.json")
        _, resolved = alerts_of("resolved.json")
        store.record_alerts(self.conn, gk, firing, "2026-11-13T11:17:30.000Z")
        out = store.record_alerts(self.conn, gk, resolved, "2026-11-13T11:45:30.000Z")
        self.assertEqual(out, ["resolve"])
        ep = self.episodes()
        self.assertEqual(len(ep), 1)  # cùng một episode, không tạo mới
        _, starts, status, ends, _, _, first, last = ep[0]
        self.assertEqual((status, ends), ("resolved", "2026-11-13T11:45:00.534Z"))
        self.assertEqual((first, last), ("2026-11-13T11:17:30.000Z", "2026-11-13T11:45:30.000Z"))
        self.assertEqual([e[3] for e in self.events()], ["new", "resolve"])

    def test_source_and_received_times_kept_apart(self):
        gk, resolved = alerts_of("resolved.json")
        store.record_alerts(self.conn, gk, resolved, "2026-11-13T11:45:30.000Z")
        ev = self.events()[0]
        self.assertEqual(ev[1], "2026-11-13T11:45:00.534Z")  # endsAt từ nguồn
        self.assertEqual(ev[2], "2026-11-13T11:45:30.000Z")  # giờ webhook nhận

    def test_rollback_when_one_alert_fails(self):
        gk, alerts = alerts_of("firing.json")
        broken = dict(alerts[0], starts_at="2026-11-13T12:00:00.000Z", alertname=None)
        with self.assertRaises(sqlite3.IntegrityError):
            store.record_alerts(self.conn, gk, [alerts[0], broken])
        self.assertEqual(self.episodes(), [])  # alert đầu cũng không được ghi
        self.assertEqual(self.events(), [])

    def test_labels_stored_as_json(self):
        gk, alerts = alerts_of("firing.json")
        store.record_alerts(self.conn, gk, alerts)
        labels = json.loads(self.conn.execute("SELECT labels_json FROM episodes").fetchone()[0])
        self.assertEqual(labels["service"], "moni-nginx")


if __name__ == "__main__":
    unittest.main()
