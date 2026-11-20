import copy
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import store  # noqa: E402
from app import parse_payload  # noqa: E402

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
GK, FIRING = parse_payload((FIXTURES / "firing.json").read_bytes())
_, RESOLVED = parse_payload((FIXTURES / "resolved.json").read_bytes())


def recurrence(alert, starts_at, ends_at=None):
    """Cùng alert (cùng fingerprint) nhưng là lần phát sinh mới: startsAt khác."""
    a = copy.deepcopy(alert)
    a["starts_at"] = starts_at
    if ends_at:
        a["ends_at"] = ends_at
    return a


class RulesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = store.connect(str(pathlib.Path(self.tmp.name) / "rules.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def send(self, alerts, received_at):
        return store.record_alerts(self.conn, GK, alerts, received_at)

    def episodes(self):
        return self.conn.execute(
            "SELECT starts_at, status, ends_at, missing_firing FROM episodes ORDER BY starts_at"
        ).fetchall()

    def outcomes(self):
        return [r[0] for r in self.conn.execute("SELECT outcome FROM events ORDER BY id")]

    def test_repeated_firing_keeps_one_episode(self):
        self.send(FIRING, "2026-11-13T11:17:30.000Z")
        self.send(FIRING, "2026-11-13T11:33:30.000Z")
        self.send(FIRING, "2026-11-13T11:49:30.000Z")
        self.assertEqual(len(self.episodes()), 1)
        self.assertEqual(self.outcomes(), ["new", "repeat", "repeat"])

    def test_repeated_resolved_keeps_ends_at(self):
        self.send(FIRING, "2026-11-13T11:17:30.000Z")
        self.send(RESOLVED, "2026-11-13T11:45:30.000Z")
        late_copy = recurrence(RESOLVED[0], RESOLVED[0]["starts_at"], "2026-11-13T11:59:00.000Z")
        self.send([late_copy], "2026-11-13T11:47:30.000Z")
        self.assertEqual(self.episodes(), [("2026-11-13T11:17:00.534Z", "resolved", "2026-11-13T11:45:00.534Z", 0)])
        self.assertEqual(self.outcomes(), ["new", "resolve", "resolved_repeat"])

    def test_late_firing_does_not_reopen(self):
        self.send(FIRING, "2026-11-13T11:17:30.000Z")
        self.send(RESOLVED, "2026-11-13T11:45:30.000Z")
        self.send(FIRING, "2026-11-13T11:46:00.000Z")  # bản firing cũ đến muộn
        status = self.episodes()[0][1]
        self.assertEqual(status, "resolved")
        self.assertEqual(self.outcomes(), ["new", "resolve", "late_firing"])

    def test_resolved_before_firing(self):
        self.send(RESOLVED, "2026-11-13T11:45:30.000Z")  # mất bản firing
        self.send(FIRING, "2026-11-13T11:46:00.000Z")  # firing đến sau
        self.assertEqual(self.episodes(), [("2026-11-13T11:17:00.534Z", "resolved", "2026-11-13T11:45:00.534Z", 1)])
        self.assertEqual(self.outcomes(), ["resolved_without_firing", "late_firing"])

    def test_recurrence_creates_new_episode(self):
        self.send(FIRING, "2026-11-13T11:17:30.000Z")
        self.send(RESOLVED, "2026-11-13T11:45:30.000Z")
        again = recurrence(FIRING[0], "2026-11-13T12:10:15.534Z")
        self.send([again], "2026-11-13T12:10:45.000Z")
        eps = self.episodes()
        self.assertEqual(len(eps), 2)
        self.assertEqual([e[1] for e in eps], ["resolved", "firing"])
        self.assertIsNone(eps[1][2])
        self.assertEqual(self.outcomes(), ["new", "resolve", "new"])

    def test_one_notification_mixed_states(self):
        older = recurrence(FIRING[0], "2026-11-13T10:00:00.534Z")
        self.send([older], "2026-11-13T10:00:30.000Z")
        closing = recurrence(RESOLVED[0], "2026-11-13T10:00:00.534Z", "2026-11-13T10:30:00.534Z")
        out = self.send([closing, FIRING[0]], "2026-11-13T11:17:30.000Z")
        self.assertEqual(out, ["resolve", "new"])
        self.assertEqual([e[1] for e in self.episodes()], ["resolved", "firing"])


if __name__ == "__main__":
    unittest.main()
