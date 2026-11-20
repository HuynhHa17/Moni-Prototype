import copy
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app import PayloadError, parse_payload  # noqa: E402

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def body(data):
    return json.dumps(data).encode()


class ValidPayload(unittest.TestCase):
    def test_firing(self):
        group_key, alerts = parse_payload(body(load("firing.json")))
        self.assertEqual(len(alerts), 1)
        a = alerts[0]
        self.assertEqual(a["status"], "firing")
        self.assertEqual(a["fingerprint"], "ffba5f3489ed0334")
        self.assertEqual(a["starts_at"], "2026-11-13T11:17:00.534Z")
        self.assertIsNone(a["ends_at"])  # 0001-01-01 nghĩa là chưa kết thúc
        self.assertEqual(a["host"], "workload-vm2")
        self.assertIn("ServiceHttpDown", group_key)

    def test_resolved_keeps_key(self):
        _, alerts = parse_payload(body(load("resolved.json")))
        a = alerts[0]
        self.assertEqual(a["status"], "resolved")
        self.assertEqual(a["starts_at"], "2026-11-13T11:17:00.534Z")
        self.assertEqual(a["ends_at"], "2026-11-13T11:45:00.534Z")

    def test_status_per_alert_not_group(self):
        data = load("firing.json")
        second = copy.deepcopy(data["alerts"][0])
        second["status"] = "resolved"
        second["endsAt"] = "2026-11-13T11:45:00.534Z"
        data["alerts"].append(second)  # nhóm ghi firing, alert thứ 2 đã resolved
        _, alerts = parse_payload(body(data))
        self.assertEqual([a["status"] for a in alerts], ["firing", "resolved"])


class InvalidPayload(unittest.TestCase):
    def assertRejected(self, raw, words):
        with self.assertRaises(PayloadError) as ctx:
            parse_payload(raw)
        self.assertIn(words, str(ctx.exception))

    def test_not_json(self):
        self.assertRejected(b"hello", "không phải JSON")

    def test_wrong_version(self):
        data = load("firing.json")
        data["version"] = "3"
        self.assertRejected(body(data), "version 4")

    def test_empty_alerts(self):
        data = load("firing.json")
        data["alerts"] = []
        self.assertRejected(body(data), "không rỗng")

    def test_bad_status(self):
        data = load("firing.json")
        data["alerts"][0]["status"] = "ok"
        self.assertRejected(body(data), "alerts[0].status")

    def test_missing_fingerprint(self):
        data = load("firing.json")
        del data["alerts"][0]["fingerprint"]
        self.assertRejected(body(data), "fingerprint")

    def test_zero_starts_at(self):
        data = load("firing.json")
        data["alerts"][0]["startsAt"] = "0001-01-01T00:00:00Z"
        self.assertRejected(body(data), "startsAt")

    def test_missing_alertname(self):
        data = load("firing.json")
        del data["alerts"][0]["labels"]["alertname"]
        self.assertRejected(body(data), "alertname")


if __name__ == "__main__":
    unittest.main()
