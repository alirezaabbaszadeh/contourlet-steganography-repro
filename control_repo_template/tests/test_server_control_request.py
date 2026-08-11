from __future__ import annotations

import unittest

from control.request import RequestError, parse_request


SHA = "a" * 40
REPOSITORY = "alirezaabbaszadeh/contourlet-steganography-repro"


class ServerControlRequestTests(unittest.TestCase):
    def base(self, command: str, **extra: object) -> dict[str, object]:
        return {
            "schema_version": 1,
            "command": command,
            "scientific_repository": REPOSITORY,
            "scientific_commit": SHA,
            **extra,
        }

    def test_accepts_health_check(self) -> None:
        request = parse_request(self.base("health_check"))
        self.assertEqual(request.command, "health_check")
        self.assertEqual(request.scientific_commit, SHA)
        self.assertIsNone(request.workers)

    def test_accepts_worker_count_at_7(self) -> None:
        request = parse_request(self.base("worker_benchmark", workers=7))
        self.assertEqual(request.workers, 7)

    def test_rejects_worker_count_above_7(self) -> None:
        with self.assertRaisesRegex(RequestError, "maximum worker count is 7"):
            parse_request(self.base("worker_benchmark", workers=8))

    def test_rejects_unknown_command(self) -> None:
        with self.assertRaisesRegex(RequestError, "unknown command"):
            parse_request(self.base("shell"))

    def test_rejects_floating_ref(self) -> None:
        payload = self.base("runtime_check")
        payload["scientific_commit"] = "main"
        with self.assertRaisesRegex(RequestError, "40-character"):
            parse_request(payload)

    def test_rejects_unknown_field(self) -> None:
        with self.assertRaisesRegex(RequestError, "unknown fields"):
            parse_request(self.base("health_check", shell="id"))

    def test_rejects_wrong_repository(self) -> None:
        payload = self.base("health_check")
        payload["scientific_repository"] = "example/other"
        with self.assertRaisesRegex(RequestError, "unexpected scientific repository"):
            parse_request(payload)

    def test_rejects_boolean_worker_count(self) -> None:
        with self.assertRaisesRegex(RequestError, "positive integer"):
            parse_request(self.base("worker_benchmark", workers=True))


if __name__ == "__main__":
    unittest.main()
