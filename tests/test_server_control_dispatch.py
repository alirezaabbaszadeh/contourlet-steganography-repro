from __future__ import annotations

from pathlib import Path
import unittest

from control.dispatch import CONTROL_CONFIG, build_operation
from control.request import parse_request


SHA = "b" * 40
REPOSITORY = "alirezaabbaszadeh/contourlet-steganography-repro"
CHECKOUT = "/srv/ctsteg/control/scientific-repo"


class ServerControlDispatchTests(unittest.TestCase):
    def request(self, command: str, **extra: object):
        return parse_request(
            {
                "schema_version": 1,
                "command": command,
                "scientific_repository": REPOSITORY,
                "scientific_commit": SHA,
                **extra,
            }
        )

    def test_health_check_uses_fixed_control_module(self) -> None:
        argv = build_operation(self.request("health_check"), CHECKOUT)
        self.assertEqual(
            argv,
            [
                "python3",
                "-m",
                "control.operations",
                "health_check",
                "--checkout",
                str(Path(CHECKOUT)),
                "--config",
                CONTROL_CONFIG,
            ],
        )

    def test_worker_count_is_a_separate_numeric_argument(self) -> None:
        argv = build_operation(
            self.request("worker_benchmark", workers=44),
            CHECKOUT,
        )
        self.assertEqual(argv[-2:], ["--workers", "44"])
        self.assertNotIn("44;", " ".join(argv))

    def test_all_allowlisted_commands_use_same_fixed_module(self) -> None:
        for command in (
            "health_check",
            "runtime_check",
            "bootstrap_check",
            "research_status",
            "run_final_5j",
        ):
            with self.subTest(command=command):
                argv = build_operation(self.request(command), CHECKOUT)
                self.assertEqual(argv[:4], ["python3", "-m", "control.operations", command])


if __name__ == "__main__":
    unittest.main()
