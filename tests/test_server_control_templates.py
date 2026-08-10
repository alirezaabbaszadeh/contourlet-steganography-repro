from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "control_repo_template"


class ServerControlTemplateTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (TEMPLATE / relative).read_text(encoding="utf-8")

    def test_ci_uses_only_github_hosted_runner(self) -> None:
        text = self.read(".github/workflows/ci.yml")
        self.assertIn("runs-on: ubuntu-latest", text)
        self.assertNotIn("self-hosted", text)

    def test_server_control_is_push_only_on_requests(self) -> None:
        text = self.read(".github/workflows/server-control.yml")
        self.assertIn("requests/*.json", text)
        self.assertIn("self-hosted", text)
        self.assertIn("ctsteg-ferdowsi-48", text)
        self.assertIn("python3 -m control.head_request", text)
        self.assertNotIn("pull_request", text)
        self.assertNotIn("workflow_dispatch", text)

    def test_manual_health_has_no_untrusted_inputs(self) -> None:
        text = self.read(".github/workflows/server-health.yml")
        self.assertIn("workflow_dispatch", text)
        self.assertIn("ctsteg-ferdowsi-48", text)
        self.assertIn("control.operations health_check", text)
        self.assertNotIn("pull_request", text)
        self.assertNotIn("inputs:", text)

    def test_control_config_example_contains_only_absolute_paths(self) -> None:
        payload = json.loads(self.read("config/ctsteg-control.example.json"))
        self.assertEqual(payload["schema_version"], 1)
        for key, value in payload.items():
            if key == "schema_version":
                continue
            self.assertTrue(Path(value).is_absolute(), key)
        self.assertEqual(
            payload["final_control_helper"],
            "/usr/local/sbin/ctsteg-control-final",
        )

    def test_privileged_helper_has_fixed_service_and_actions(self) -> None:
        text = self.read("server/ctsteg-control-final")
        self.assertIn("ctsteg-research@final.service", text)
        self.assertIn('"start")', text)
        self.assertIn('"status")', text)
        self.assertNotIn("eval ", text)

    def test_sudoers_grants_only_fixed_helper_actions(self) -> None:
        text = self.read("server/ctsteg-control-final.sudoers")
        self.assertIn("/usr/local/sbin/ctsteg-control-final start", text)
        self.assertIn("/usr/local/sbin/ctsteg-control-final status", text)
        self.assertNotIn("/bin/bash", text)
        self.assertNotIn("systemctl", text)
        self.assertNotIn("ALL=(ALL) NOPASSWD: ALL", text)


if __name__ == "__main__":
    unittest.main()
