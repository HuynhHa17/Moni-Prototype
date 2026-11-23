import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "monitoring/grafana/dashboards/host.json"


class HostDashboardTests(unittest.TestCase):
    def setUp(self):
        self.dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
        self.panels = {panel["id"]: panel for panel in self.dashboard["panels"]}

    def test_http_result_requires_successful_http_scrape(self):
        expression = self.panels[1]["targets"][0]["expr"]
        self.assertIn('probe_success{job="http",host="$host"}', expression)
        self.assertIn('(up{job="http",host="$host"} == 1)', expression)
        self.assertIn("vector(-1)", expression)

    def test_missing_node_and_blackbox_data_use_unknown_fallback(self):
        node_expression = self.panels[2]["targets"][0]["expr"]
        blackbox_expression = self.panels[3]["targets"][0]["expr"]
        self.assertIn("vector(-1)", node_expression)
        self.assertIn("vector(-1)", blackbox_expression)

    def test_http_timeline_does_not_turn_missing_data_into_failure(self):
        expression = self.panels[8]["targets"][0]["expr"]
        self.assertIn('(up{job="http",host="$host"} == 1)', expression)
        self.assertIn("vector(-1)", expression)

    def test_status_maps_expose_unknown_failure_and_success(self):
        expected_mappings = {
            "-1": "CHƯA XÁC ĐỊNH",
            "0": "HTTP THẤT BẠI",
            "1": "HTTP ĐẠT",
        }
        defaults = self.panels[1]["fieldConfig"]["defaults"]
        mappings = defaults["mappings"][0]["options"]
        self.assertEqual(
            {key: mappings[key]["text"] for key in mappings},
            expected_mappings,
        )
        self.assertEqual(defaults["noValue"], "CHƯA XÁC ĐỊNH")

    def test_host_variable_includes_all_labeled_scrape_jobs(self):
        host_variable = self.dashboard["templating"]["list"][0]
        self.assertEqual(host_variable["definition"], "label_values(up, host)")
        self.assertEqual(host_variable["query"]["query"], "label_values(up, host)")

    def test_network_panel_uses_rate_in_bits_and_excludes_virtual_interfaces(self):
        panel = self.panels[9]
        self.assertEqual(panel["fieldConfig"]["defaults"]["unit"], "bps")
        expressions = [target["expr"] for target in panel["targets"]]
        self.assertEqual(len(expressions), 2)
        for metric, expression in zip(("receive", "transmit"), expressions):
            self.assertIn(f"node_network_{metric}_bytes_total", expression)
            self.assertIn("8 * rate(", expression)
            self.assertIn('device!~"lo|veth.*|docker.*|br-.*|virbr.*"', expression)
            self.assertIn('(up{job="node",host="$host"} == 1)', expression)

    def test_uptime_uses_boot_time_not_up(self):
        panel = self.panels[10]
        expression = panel["targets"][0]["expr"]
        self.assertTrue(expression.startswith("(time() - node_boot_time_seconds{"))
        self.assertIn('(up{job="node",host="$host"} == 1)', expression)
        self.assertEqual(panel["fieldConfig"]["defaults"]["noValue"], "CHƯA XÁC ĐỊNH")


if __name__ == "__main__":
    unittest.main()
