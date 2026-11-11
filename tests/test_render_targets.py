import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("render_targets", ROOT / "scripts/render_targets.py")
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)


class TargetRenderingTests(unittest.TestCase):
    def test_individual_lab_uses_own_address(self):
        result = render.build_targets({"WORKLOAD_IP": "192.0.2.21", "WORKLOAD_HOST": "alice-workload", "WORKLOAD_HTTP_PORT": "8181"})
        self.assertEqual(result["node.json"], [{"targets": ["192.0.2.21:9100"], "labels": {"host": "alice-workload", "environment": "lab"}}])
        self.assertEqual(result["http.json"][0]["targets"], ["http://192.0.2.21:8181/health"])

    def test_integration_lab_keeps_separate_hosts(self):
        result = render.build_targets({"WORKLOAD_IP": "192.0.2.21", "WORKLOAD_VM3_IP": "192.0.2.22"})
        self.assertEqual([entry["labels"]["host"] for entry in result["node.json"]], ["workload-vm2", "workload-vm3"])
        self.assertEqual(len(result["http.json"]), 2)

    def test_ipv6_authority(self):
        result = render.build_targets({"WORKLOAD_IP": "2001:db8::21"})
        self.assertEqual(result["http.json"][0]["targets"], ["http://[2001:db8::21]:8080/health"])

    def test_invalid_inventory_rejected(self):
        for values in ({"WORKLOAD_IP": "CHANGE_ME"}, {"WORKLOAD_IP": "127.0.0.1"},
                       {"WORKLOAD_IP": "192.0.2.21", "WORKLOAD_HTTP_PORT": "65536"},
                       {"WORKLOAD_IP": "192.0.2.21", "WORKLOAD_HOST": "bad host"},
                       {"WORKLOAD_IP": "192.0.2.21", "WORKLOAD_VM3_IP": "192.0.2.21"},
                       {"WORKLOAD_IP": "192.0.2.21", "WORKLOAD_VM3_IP": "192.0.2.22", "WORKLOAD_VM3_HOST": "workload-vm2"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                render.build_targets(values)

    def test_cli_does_not_replace_valid_targets_on_bad_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            env = path / ".env"
            output = path / "targets"
            env.write_text("WORKLOAD_IP=192.0.2.21\n", encoding="utf-8")
            command = [sys.executable, str(ROOT / "scripts/render_targets.py"), "--env-file", str(env), "--output-dir", str(output)]
            good = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            previous = {file.name: file.read_bytes() for file in output.iterdir()}
            self.assertEqual(len(json.loads(previous["node.json"])), 1)
            env.write_text("WORKLOAD_IP=CHANGE_ME\n", encoding="utf-8")
            bad = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertEqual(previous, {file.name: file.read_bytes() for file in output.iterdir()})

    def test_env_does_not_execute_expressions(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / ".env"
            for content in ("WORKLOAD_IP=$(anything)\n", "WORKLOAD_IP=a\nWORKLOAD_IP=b\n", "WORKLOAD_IP='broken\n"):
                env.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    render.read_env(env)

    def test_unused_secret_does_not_get_rendered(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / ".env"
            env.write_text("WORKLOAD_IP=192.0.2.21\nGRAFANA_PASSWORD='literal$secret'\n", encoding="utf-8")
            result = render.build_targets(render.read_env(env))
            self.assertNotIn("secret", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
