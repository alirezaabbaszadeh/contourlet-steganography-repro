"""Machine-checkable contract for the mandatory interruption/recovery gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .provenance import sha256_file, sha256_json
from .runtime import read_json


_RUNTIME_FILES = (
    "cli.py",
    "runtime.py",
    "runtime_gate_contract.py",
    "digital_ad/research_runtime.py",
    "digital_ad/runtime_gate.py",
    "digital_ad/runtime_probe.py",
)


def runtime_gate_fingerprint() -> str:
    package = Path(__file__).resolve().parent
    records = [
        {"path": relative, "sha256": sha256_file(package / relative)}
        for relative in _RUNTIME_FILES
    ]
    return sha256_json({"schema": 1, "files": records})


def validate_runtime_gate_report(
    path: str | Path,
) -> dict[str, Any]:
    report_path = Path(path).resolve()
    if not report_path.is_file():
        raise FileNotFoundError(f"runtime gate report not found: {report_path}")
    report = read_json(report_path)
    if not isinstance(report, dict):
        raise ValueError("runtime gate report must be a JSON object")
    checks = {
        "gate_identity": report.get("gate") == "parallel-cache-resume-export",
        "status": report.get("status") == "passed",
        "runtime_fingerprint": (
            report.get("runtime_gate_fingerprint")
            == runtime_gate_fingerprint()
        ),
        "real_sigkill": (
            report.get("interruption", {}).get("signal") == "SIGKILL"
            and report.get("interruption", {}).get("first_exit_code") == -9
        ),
        "cache_reused": (
            int(report.get("resume", {}).get("cache_hits", 0))
            >= int(
                report.get("interruption", {}).get(
                    "valid_objects_before_restart",
                    1,
                )
            )
        ),
        "objects_unchanged": (
            int(
                report.get("interruption", {}).get(
                    "unchanged_after_restart",
                    0,
                )
            )
            >= int(
                report.get("interruption", {}).get(
                    "valid_objects_before_restart",
                    1,
                )
            )
        ),
        "archive_checksums": (
            report.get("archive_validation", {}).get("status") == "passed"
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError(f"runtime gate report failed checks: {failed}")
    return {
        "schema": 1,
        "path": str(report_path),
        "sha256": sha256_file(report_path),
        "gate_id": report.get("gate_id"),
        "runtime_gate_fingerprint": report["runtime_gate_fingerprint"],
        "checks": checks,
    }
