import json
import logging
import pathlib
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import app  # noqa: E402

FIRING = (pathlib.Path(__file__).parent / "fixtures" / "firing.json").read_bytes()


class HttpTest(unittest.TestCase):
    def start(self, db_path):
        server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        server.db_path = db_path
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def call(self, url, data=None):
        req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.good_db = str(pathlib.Path(self.tmp.name) / "ok.db")
        self.bad_db = str(pathlib.Path(self.tmp.name) / "khong-co-thu-muc" / "x.db")

    def test_health_ok(self):
        base = self.start(self.good_db)
        code, body = self.call(base + "/health")
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "ok")
        self.assertIn("không kiểm tra Alertmanager", body["scope"])

    def test_health_reports_db_error(self):
        base = self.start(self.bad_db)
        code, body = self.call(base + "/health")
        self.assertEqual(code, 503)
        self.assertEqual(body["status"], "error")

    def test_post_returns_500_when_db_fails(self):
        base = self.start(self.bad_db)
        code, body = self.call(base + "/alerts", FIRING)
        self.assertEqual(code, 500)  # Alertmanager gửi lại khi nhận 5xx
        self.assertIn("CSDL", body["error"])

    def test_post_ok_then_logs_without_sensitive_data(self):
        base = self.start(self.good_db)
        with self.assertLogs("webhook", level="INFO") as logs:
            code, body = self.call(base + "/alerts", FIRING)
        self.assertEqual((code, body["outcomes"]), (200, ["new"]))
        text = "\n".join(logs.output)
        self.assertIn("fingerprint=ffba5f3489ed0334", text)
        self.assertNotIn("Kiểm tra Nginx", text)  # không in nội dung annotations
        self.assertNotIn("IP-LAB", text)  # không in instance/URL đích


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
