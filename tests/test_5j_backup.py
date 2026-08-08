from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SYNC = REPOSITORY_ROOT / "scripts/5j/sync_completed_objects.py"
VERIFY = REPOSITORY_ROOT / "scripts/5j/verify_remote_backup.py"
EVACUATE = REPOSITORY_ROOT / "scripts/5j/evacuate_server.py"


class BackupLifecycleTests(unittest.TestCase):
    def _run(self, *arguments: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *(str(argument) for argument in arguments)],
            cwd=REPOSITORY_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    @staticmethod
    def _write_inventory(
        path: Path,
        *,
        run_id: str,
        objects: list[dict[str, object]],
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "protocol_id": "FINAL-5J-v1",
                    "run_id": run_id,
                    "objects": objects,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_filesystem_backup_restore_verify_and_evacuation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            server = root / "server"
            remote = root / "remote"
            staging = root / "staging"
            control = root / "control"
            server.mkdir()
            control.mkdir()

            public_object = server / "result.json"
            encrypted_object = server / "restricted-evidence.age"
            public_object.write_text('{"result":"ok"}\n', encoding="utf-8")
            encrypted_object.write_bytes(b"age-encrypted-fixture\x00\x01")

            inventory = control / "inventory.json"
            ledger = control / "ledger.json"
            report = control / "evacuation.json"
            self._write_inventory(
                inventory,
                run_id="fixture-run-0001",
                objects=[
                    {
                        "object_id": "result-object",
                        "kind": "evaluation",
                        "path": str(public_object),
                        "classification": "public",
                        "encryption": "none",
                    },
                    {
                        "object_id": "restricted-object",
                        "kind": "private_evidence_ciphertext",
                        "path": str(encrypted_object),
                        "classification": "restricted",
                        "encryption": "client_side_encrypted",
                    },
                ],
            )

            sync = self._run(
                SYNC,
                "--inventory",
                inventory,
                "--ledger",
                ledger,
                "--staging-dir",
                staging,
                "--backend",
                "filesystem",
                "--remote-root",
                remote,
                "--max-bundle-bytes",
                1024 * 1024,
                "--json",
            )
            self.assertEqual(sync.returncode, 0, sync.stdout)
            ledger_payload = json.loads(ledger.read_text(encoding="utf-8"))
            self.assertEqual(len(ledger_payload["objects"]), 2)
            self.assertEqual(len(ledger_payload["bundles"]), 1)
            self.assertTrue(
                all(
                    item["state"] == "committed_complete"
                    for item in ledger_payload["objects"]
                )
            )
            bundle = ledger_payload["bundles"][0]
            self.assertEqual(bundle["state"], "committed_complete")
            self.assertTrue((remote / bundle["asset_name"]).is_file())

            verify = self._run(VERIFY, "--ledger", ledger, "--json")
            self.assertEqual(verify.returncode, 0, verify.stdout)

            evacuation = self._run(
                EVACUATE,
                "--ledger",
                ledger,
                "--root",
                server,
                "--report",
                report,
                "--json",
            )
            self.assertEqual(evacuation.returncode, 0, evacuation.stdout)
            evacuation_payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(evacuation_payload["evacuation_ready"])
            self.assertTrue(
                all(value == 0 for value in evacuation_payload["counts"].values())
            )

            untracked_log = server / "late.log"
            untracked_log.write_text("not backed up\n", encoding="utf-8")
            blocked = self._run(
                EVACUATE,
                "--ledger",
                ledger,
                "--root",
                server,
                "--report",
                report,
                "--json",
            )
            self.assertEqual(blocked.returncode, 2, blocked.stdout)
            blocked_payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertFalse(blocked_payload["evacuation_ready"])
            self.assertEqual(blocked_payload["counts"]["unique_server_only_files"], 1)
            self.assertEqual(blocked_payload["counts"]["unuploaded_logs"], 1)

    def test_plaintext_secret_inventory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            secret = root / "C8-privateKey.pem"
            begin = "-----BEGIN " + "PRIVATE KEY-----"
            end = "-----END " + "PRIVATE KEY-----"
            secret.write_text(
                f"{begin}\nfixture\n{end}\n",
                encoding="utf-8",
            )
            inventory = root / "inventory.json"
            self._write_inventory(
                inventory,
                run_id="fixture-run-0002",
                objects=[
                    {
                        "object_id": "plaintext-secret",
                        "kind": "ssh_private_key",
                        "path": str(secret),
                        "classification": "secret",
                        "encryption": "none",
                    }
                ],
            )
            result = self._run(
                SYNC,
                "--inventory",
                inventory,
                "--ledger",
                root / "ledger.json",
                "--staging-dir",
                root / "staging",
                "--backend",
                "filesystem",
                "--remote-root",
                root / "remote",
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("must be client-side encrypted", result.stdout)

    def test_remote_tampering_revokes_committed_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            server = root / "server"
            remote = root / "remote"
            server.mkdir()
            payload = server / "result.bin"
            payload.write_bytes(b"verified result")
            inventory = root / "inventory.json"
            ledger = root / "ledger.json"
            self._write_inventory(
                inventory,
                run_id="fixture-run-0003",
                objects=[
                    {
                        "object_id": "tamper-target",
                        "kind": "evaluation",
                        "path": str(payload),
                        "classification": "public",
                        "encryption": "none",
                    }
                ],
            )
            sync = self._run(
                SYNC,
                "--inventory",
                inventory,
                "--ledger",
                ledger,
                "--staging-dir",
                root / "staging",
                "--backend",
                "filesystem",
                "--remote-root",
                remote,
            )
            self.assertEqual(sync.returncode, 0, sync.stdout)
            ledger_payload = json.loads(ledger.read_text(encoding="utf-8"))
            remote_asset = remote / ledger_payload["bundles"][0]["asset_name"]
            with remote_asset.open("ab") as stream:
                stream.write(b"tampered")

            verify = self._run(VERIFY, "--ledger", ledger, "--json")
            self.assertEqual(verify.returncode, 2, verify.stdout)
            revised = json.loads(ledger.read_text(encoding="utf-8"))
            self.assertEqual(revised["bundles"][0]["state"], "uploaded")
            self.assertEqual(revised["objects"][0]["state"], "uploaded")
            self.assertIsNone(revised["objects"][0]["remote_verified_at"])


if __name__ == "__main__":
    unittest.main()
