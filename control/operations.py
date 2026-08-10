from __future__ import annotations

from pathlib import Path
from typing import Mapping


FINAL_HELPER = "/usr/local/sbin/ctsteg-control-final"
REQUIRED_PATH_FIELDS = (
    "bootstrap_config",
    "plan",
    "runtime_bindings",
    "science_ready_report",
    "output_root",
    "cache_dir",
    "engineering_manifest",
    "engineering_cache_dir",
    "engineering_run_dir",
    "final_control_helper",
)


class OperationError(ValueError):
    pass


def validate_config(payload: Mapping[str, object]) -> dict[str, str]:
    if payload.get("schema_version") != 1:
        raise OperationError("control config schema_version must be 1")

    normalized: dict[str, str] = {}
    for field in REQUIRED_PATH_FIELDS:
        value = payload.get(field)
        if not isinstance(value, str) or not value:
            raise OperationError(f"control config field {field} must be a non-empty string")
        if not Path(value).is_absolute():
            raise OperationError(f"control config field {field} must be an absolute path")
        normalized[field] = value

    if normalized["final_control_helper"] != FINAL_HELPER:
        raise OperationError(f"final_control_helper must be {FINAL_HELPER}")

    return normalized


def build_scientific_argv(
    command: str,
    payload: Mapping[str, object],
    checkout: Path,
    *,
    workers: int | None = None,
) -> list[str]:
    config = validate_config(payload)
    checkout = Path(checkout)

    if command == "health_check":
        raise OperationError("health_check is a native operation")

    if command == "bootstrap_check":
        return [
            str(checkout / "scripts/bootstrap_ubuntu_server.sh"),
            "--check",
            "--config",
            config["bootstrap_config"],
        ]

    if command == "worker_benchmark":
        if not isinstance(workers, int) or isinstance(workers, bool) or workers < 1:
            raise OperationError("workers must be a positive integer")
        if workers > 44:
            raise OperationError("maximum worker count is 44")
        return [
            "python3",
            str(checkout / "scripts/5j/run_engineering_worker_trial.py"),
            "--manifest",
            config["engineering_manifest"],
            "--runtime-bindings",
            config["runtime_bindings"],
            "--repository-root",
            str(checkout),
            "--cache-dir",
            config["engineering_cache_dir"],
            "--run-dir",
            config["engineering_run_dir"],
            "--json",
            "--workers",
            str(workers),
        ]

    if command == "runtime_check":
        return [
            "python3",
            str(checkout / "scripts/5j/run_research.py"),
            "--plan",
            config["plan"],
            "--runtime-bindings",
            config["runtime_bindings"],
            "--repository-root",
            str(checkout),
            "--science-ready-report",
            config["science_ready_report"],
            "--output-root",
            config["output_root"],
            "--cache-dir",
            config["cache_dir"],
            "--json",
        ]

    if command == "research_status":
        return [
            "python3",
            str(checkout / "scripts/5j/research_status.py"),
            "--plan",
            config["plan"],
            "--cache-dir",
            config["cache_dir"],
            "--json",
        ]

    if command == "run_final_5j":
        return ["sudo", "-n", config["final_control_helper"], "start"]

    raise OperationError(f"unsupported operation: {command}")
