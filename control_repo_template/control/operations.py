from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from typing import Mapping, Sequence


FINAL_HELPER = "/usr/local/sbin/ctsteg-control-final"
MAXIMUM_WORKERS = 29
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
TIMEOUT_SECONDS = {
    "bootstrap_check": 1800,
    "worker_benchmark": 10800,
    "runtime_check": 1800,
    "research_status": 300,
    "run_final_5j": 60,
}


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


def _meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        lines = Path("/proc/meminfo").read_text(encoding="ascii").splitlines()
    except OSError as exc:
        raise OperationError(f"cannot read /proc/meminfo: {exc}") from exc
    for line in lines:
        key, _, raw_value = line.partition(":")
        parts = raw_value.split()
        if not parts:
            continue
        try:
            value = int(parts[0])
        except ValueError:
            continue
        if len(parts) > 1 and parts[1].lower() == "kb":
            value *= 1024
        values[key] = value
    return values


def collect_health_snapshot() -> dict[str, object]:
    memory = _meminfo()
    disk = shutil.disk_usage("/")
    return {
        "hostname": socket.gethostname(),
        "logical_cpus": os.cpu_count() or 1,
        "memory_total_bytes": int(memory.get("MemTotal", 0)),
        "memory_available_bytes": int(memory.get("MemAvailable", 0)),
        "swap_total_bytes": int(memory.get("SwapTotal", 0)),
        "disk_total_bytes": int(disk.total),
        "disk_free_bytes": int(disk.free),
        "python_executable": sys.executable,
        "git_executable": shutil.which("git"),
        "octave_executable": shutil.which("octave"),
    }


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
        if workers > MAXIMUM_WORKERS:
            raise OperationError(f"maximum worker count is {MAXIMUM_WORKERS}")
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


def load_control_config(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise OperationError(f"control config is not readable: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OperationError(f"cannot load control config {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise OperationError("control config must be a JSON object")
    validate_config(payload)
    return payload


def execute_argv(argv: Sequence[str], *, timeout_seconds: int) -> int:
    completed = subprocess.run(
        list(argv),
        check=False,
        shell=False,
        timeout=timeout_seconds,
    )
    return int(completed.returncode)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one allowlisted Ferdowsi server operation.")
    parser.add_argument(
        "command",
        choices=(
            "health_check",
            "runtime_check",
            "bootstrap_check",
            "worker_benchmark",
            "research_status",
            "run_final_5j",
        ),
    )
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--workers", type=int)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "health_check":
        print(json.dumps(collect_health_snapshot(), sort_keys=True))
        return 0

    payload = load_control_config(args.config)
    if not args.checkout.is_dir():
        raise OperationError(f"scientific checkout is not a directory: {args.checkout}")

    operation_argv = build_scientific_argv(
        args.command,
        payload,
        args.checkout,
        workers=args.workers,
    )
    return execute_argv(
        operation_argv,
        timeout_seconds=TIMEOUT_SECONDS[args.command],
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OperationError, subprocess.TimeoutExpired) as exc:
        print(f"server control operation failed: {exc}", file=sys.stderr)
        raise SystemExit(64)
