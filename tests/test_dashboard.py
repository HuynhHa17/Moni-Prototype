import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "monitoring/grafana/dashboards/host.json"


class HostDashboardTests(unittest.TestCase):
    def setUp(self):
        self.dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
        self.panels = {panel["id"]: panel for panel in self.dashboard["panels"]}
        self.content = [p for p in self.dashboard["panels"] if p["type"] != "row"]

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
            "0": "LỖI",
            "1": "ĐẠT",
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

    def test_container_panels_use_cadvisor_and_hide_lost_containers(self):
        cpu, ram, table = self.panels[11], self.panels[12], self.panels[13]
        self.assertIn("rate(container_cpu_usage_seconds_total{", cpu["targets"][0]["expr"])
        self.assertIn("container_memory_working_set_bytes{", ram["targets"][0]["expr"])
        self.assertEqual(ram["fieldConfig"]["defaults"]["unit"], "bytes")
        self.assertIn("container_last_seen", table["targets"][0]["expr"])
        self.assertIn("> time() - 60", table["targets"][0]["expr"])
        for panel in (cpu, ram, table):
            expression = panel["targets"][0]["expr"]
            self.assertIn('name!=""', expression)
            self.assertIn('(up{job="cadvisor",host="$host"} == 1)', expression)
        self.assertFalse(cpu["fieldConfig"]["defaults"]["custom"]["spanNulls"])


    def test_panels_do_not_overlap_and_fit_the_grid(self):
        cells = {}
        for panel in self.dashboard["panels"]:
            pos = panel["gridPos"]
            self.assertLessEqual(pos["x"] + pos["w"], 24, panel["title"])
            for x in range(pos["x"], pos["x"] + pos["w"]):
                for y in range(pos["y"], pos["y"] + pos["h"]):
                    self.assertNotIn((x, y), cells, f'{panel["title"]} chồng {cells.get((x, y))}')
                    cells[(x, y)] = panel["title"]

    def test_overview_row_answers_status_at_a_glance(self):
        top = sorted(
            (p for p in self.content if p["gridPos"]["y"] == 1),
            key=lambda p: p["gridPos"]["x"],
        )
        self.assertEqual(
            [p["title"] for p in top],
            ["HTTP /health", "Độ trễ HTTP", "CPU", "RAM", "Disk đầy nhất", "Uptime"],
        )

    def test_cpu_uses_same_window_and_threshold_as_rule(self):
        for pid in (4, 15):
            expression = self.panels[pid]["targets"][0]["expr"]
            self.assertIn("[2m]", expression)
            self.assertNotIn("[5m]", expression)
        steps = self.panels[4]["fieldConfig"]["defaults"]["thresholds"]["steps"]
        self.assertEqual(steps[-1]["value"], 85)
        disk_steps = self.panels[6]["fieldConfig"]["defaults"]["thresholds"]["steps"]
        self.assertEqual(disk_steps[-1]["value"], 90)

    def test_legends_do_not_show_instance_addresses(self):
        for panel in self.content:
            for target in panel.get("targets", []):
                self.assertNotIn("{{instance}}", target.get("legendFormat", ""), panel["title"])

    def test_alert_table_lists_prometheus_alerts_for_selected_host(self):
        panel = self.panels[18]
        self.assertEqual(panel["targets"][0]["expr"], 'ALERTS{host="$host"}')
        self.assertEqual(panel["fieldConfig"]["defaults"]["noValue"], "Không có cảnh báo")

    def test_collection_status_covers_every_scrape_job(self):
        jobs = {pid: self.panels[pid]["targets"][0]["expr"] for pid in (2, 3, 19)}
        self.assertIn('up{job="node",host="$host"}', jobs[2])
        self.assertIn('up{job="http",host="$host"}', jobs[3])
        self.assertIn('up{job="cadvisor",host="$host"}', jobs[19])
        for expression in jobs.values():
            self.assertIn("vector(-1)", expression)


if __name__ == "__main__":
    unittest.main()
