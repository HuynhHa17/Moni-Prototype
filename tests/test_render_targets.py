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
    def test_individual_lab_uses_own_address_and_standard_labels(self):
        result = render.build_targets({"WORKLOAD_IP": "192.0.2.21", "WORKLOAD_HOST": "alice-workload", "WORKLOAD_HTTP_PORT": "8181"})
        self.assertEqual(result["node.json"], [{
            "targets": ["192.0.2.21:9100"],
            "labels": {
                "host": "alice-workload",
                "environment": "lab",
                "site": "onprem-lab",
                "rack": "rack-01",
                "team": "infra",
                "target_id": "node-alice-workload",
            },
        }])
        self.assertEqual(result["http.json"][0]["targets"], ["http://192.0.2.21:8181/health"])
        self.assertEqual(result["http.json"][0]["labels"]["target_id"], "http-alice-workload-moni-nginx")

    def test_integration_lab_keeps_separate_hosts(self):
        result = render.build_targets({"WORKLOAD_IP": "192.0.2.21", "WORKLOAD_VM3_IP": "192.0.2.22"})
        self.assertEqual([entry["labels"]["host"] for entry in result["node.json"]], ["workload-vm2", "workload-vm3"])
        self.assertEqual(len(result["http.json"]), 2)

    def test_inventory_lists_every_expected_target_with_target_id(self):
        result = render.build_targets({"WORKLOAD_IP": "192.0.2.21", "WORKLOAD_VM3_IP": "192.0.2.22"})
        rules = result["expected.rules.yml"]["groups"][0]["rules"]
        expected = {(rule["labels"]["job"], rule["labels"]["host"]) for rule in rules}
        self.assertEqual(expected, {(job, host) for job in ("node", "http", "cadvisor")
                                    for host in ("workload-vm2", "workload-vm3")})
        for rule in rules:
            self.assertEqual(rule["record"], "moni:target_expected")
            self.assertEqual(rule["expr"], "vector(1)")
            self.assertIn("target_id", rule["labels"])
            self.assertIn("site", rule["labels"])
            self.assertIn("rack", rule["labels"])
            self.assertIn("team", rule["labels"])
        self.assertNotIn("192.0.2", json.dumps(result["expected.rules.yml"]))

    def test_inventory_yaml_supports_profiles_and_multiple_http_probes(self):
        yaml_text = """
environment: staging
defaults:
  site: onprem-lab
  rack: rack-01
  team: infra
hosts:
  - host: workload-vm2
    address: 192.0.2.21
    team: app
    profiles: [node, http, cadvisor]
    cadvisor_port: 8081
    http_probes:
      - service: moni-nginx
        port: 8080
        path: /health
      - service: podinfo
        port: 8080
        path: /app/healthz
  - host: dc-ups-01
    address: 192.0.2.50
    team: idc
    profiles: [snmp]
    snmp_port: 1161
    snmp_module: ups_mib
"""
        with tempfile.TemporaryDirectory() as directory:
            inv_path = Path(directory) / "inventory.yml"
            inv_path.write_text(yaml_text, encoding="utf-8")
            result = render.build_targets_from_inventory(render.read_inventory(inv_path))
        self.assertEqual(len(result["node.json"]), 1)
        self.assertEqual(len(result["http.json"]), 2)
        http_ids = [item["labels"]["target_id"] for item in result["http.json"]]
        self.assertEqual(http_ids, ["http-workload-vm2-moni-nginx", "http-workload-vm2-podinfo"])
        self.assertEqual(result["snmp.json"][0]["targets"], ["192.0.2.50:1161"])
        self.assertEqual(result["snmp.json"][0]["labels"]["team"], "idc")
        self.assertNotIn("192.0.2", json.dumps(result["expected.rules.yml"]))

    def test_cadvisor_target_uses_own_port(self):
        result = render.build_targets({"WORKLOAD_IP": "192.0.2.21", "WORKLOAD_CADVISOR_PORT": "8090"})
        self.assertEqual(result["cadvisor.json"][0]["targets"], ["192.0.2.21:8090"])
        self.assertEqual(result["cadvisor.json"][0]["labels"]["target_id"], "cadvisor-workload-vm2")
        with self.assertRaises(ValueError):
            render.build_targets({"WORKLOAD_IP": "192.0.2.21", "WORKLOAD_CADVISOR_PORT": "8080"})

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
