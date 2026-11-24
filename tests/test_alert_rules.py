from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
RULES = sorted((ROOT / "monitoring/prometheus/rules").glob("*.yml"))
CATALOG = (ROOT / "docs/alerts.md").read_text(encoding="utf-8")
REQUIRED = ("summary", "description", "action", "dashboard", "runbook")


def alerts():
    for path in RULES:
        name = None
        annotations = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"\s*- alert: (\w+)", line)
            if match:
                if name:
                    yield name, annotations
                name, annotations = match.group(1), {}
                continue
            match = re.match(r"\s+(summary|description|action|dashboard|runbook): \"(.*)\"$", line)
            if name and match:
                annotations[match.group(1)] = match.group(2)
        if name:
            yield name, annotations


class AlertContentTests(unittest.TestCase):
    def test_rules_are_found(self):
        self.assertGreaterEqual(len(list(alerts())), 6)

    def test_every_alert_has_actionable_content(self):
        for name, annotations in alerts():
            with self.subTest(alert=name):
                self.assertEqual(sorted(annotations), sorted(REQUIRED))

    def test_runbook_points_to_catalog_section(self):
        for name, annotations in alerts():
            with self.subTest(alert=name):
                self.assertEqual(annotations["runbook"], f"docs/alerts.md#{name.lower()}")
                self.assertIn(f"\n## {name}\n", CATALOG)

    def test_dashboard_link_is_relative(self):
        for name, annotations in alerts():
            with self.subTest(alert=name):
                self.assertTrue(annotations["dashboard"].startswith("/d/moni-vm2/"))

    def test_content_has_no_fixed_address(self):
        address = re.compile(r"\b\d{1,3}(\.\d{1,3}){3}\b|https?://")
        for name, annotations in alerts():
            with self.subTest(alert=name):
                for value in annotations.values():
                    self.assertIsNone(address.search(value), value)


if __name__ == "__main__":
    unittest.main()
