#!/usr/bin/env python3
"""Read-only Ubuntu server preflight for the CTSteg research deployment."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import tempfile
import time
from typing import Any
from urllib.request import Request, urlopen


SUPPORTED_UBUNTU = {"22.04", "24.04"}
NETWORK_TARGETS = {
    "mathworks": "https://www.mathworks.com/mpm/glnxa64/mpm",
    "github": "https://github.com",
    "usc_sipi": "https://sipi.usc.edu/database/database.php?volume=misc",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_key_values(path: Path, separator: str = "=") -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        key, found, value = line.partition(separator)
        if not found or not key.strip():
            continue
        values[key.strip()] = value.strip().strip("\"'")
    return values


def memory_bytes() -> int | None:
    values = read_key_values(Path("/proc/meminfo"), ":")
    raw = values.get("MemTotal")
    if raw is None:
        return None
    first = raw.split()[0]
    return int(first) * 1024 if first.isdigit() else None


def cpu_facts() -> dict[str, Any]:
    try:
        text = Path("/proc/cpuinfo").read_text(encoding="utf-8")
    except OSError:
        text = ""
    processors = [
        block for block in text.split("\n\n") if "processor" in block
    ]
    first = read_key_values(
        Path("/proc/cpuinfo"),
        ":",
    )
    flags: set[str] = set()
    model = None
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            continue
        if key.strip() in {"flags", "Features"}:
            flags.update(value.split())
        elif key.strip() == "model name" and model is None:
            model = value.strip()
    return {
        "logical_cpus": os.cpu_count() or len(processors) or 1,
        "model": model or first.get("model name"),
        "avx2": "avx2" in flags,
        "flags_recorded": bool(flags),
    }


def sudo_facts() -> dict[str, Any]:
    if os.geteuid() == 0:
        return {
            "effective_uid": 0,
            "mode": "root",
            "passwordless": True,
        }
    sudo = shutil.which("sudo")
    if sudo is None:
        return {
            "effective_uid": os.geteuid(),
            "mode": "unavailable",
            "passwordless": False,
        }
    try:
        completed = subprocess.run(
            [sudo, "-n", "true"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "effective_uid": os.geteuid(),
            "mode": "error",
            "passwordless": False,
            "error": str(error),
        }
    return {
        "effective_uid": os.geteuid(),
        "mode": "passwordless_sudo" if completed.returncode == 0 else "password_required",
        "passwordless": completed.returncode == 0,
        "diagnostic": completed.stderr.strip(),
    }


def _network_target_facts(
    name: str,
    url: str,
    *,
    timeout: float,
    attempts: int,
    initial_backoff_seconds: float,
    sleep: Any = time.sleep,
) -> tuple[str, dict[str, Any]]:
    errors: list[dict[str, str]] = []
    delay = initial_backoff_seconds
    for attempt in range(1, attempts + 1):
        request = Request(
            url,
            headers={
                "User-Agent": "ctsteg-server-preflight/1",
                "Range": "bytes=0-0",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                response.read(1)
                return name, {
                    "ok": True,
                    "attempts": attempt,
                    "status": getattr(response, "status", None),
                    "final_url": response.geturl(),
                    "prior_errors": errors,
                }
        except Exception as error:  # network stacks expose several subclasses
            errors.append(
                {
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )
            if attempt < attempts:
                sleep(delay)
                delay = min(delay * 2, 30.0)
    last = errors[-1]
    return name, {
        "ok": False,
        "attempts": attempts,
        "error_type": last["error_type"],
        "error": last["error"],
        "errors": errors,
    }


def network_facts(
    timeout: float,
    *,
    attempts: int = 4,
    initial_backoff_seconds: float = 2.0,
) -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=len(NETWORK_TARGETS)) as executor:
        futures = {
            name: executor.submit(
                _network_target_facts,
                name,
                url,
                timeout=timeout,
                attempts=attempts,
                initial_backoff_seconds=initial_backoff_seconds,
            )
            for name, url in NETWORK_TARGETS.items()
        }
        return {
            name: futures[name].result()[1]
            for name in NETWORK_TARGETS
        }


def classify_failure(
    hard_blockers: list[str],
    failed_network: list[str],
) -> str:
    if not hard_blockers:
        return "ready"
    network_blocker = (
        "outbound HTTPS failed for: " + ", ".join(failed_network)
        if failed_network
        else None
    )
    if network_blocker is not None and hard_blockers == [network_blocker]:
        return "transient_network"
    return "hard_blocked"


def command_facts() -> dict[str, str | None]:
    return {
        name: shutil.which(name)
        for name in (
            "bash",
            "curl",
            "git",
            "python3",
            "systemctl",
            "tar",
            "unzip",
        )
    }


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                payload,
                stream,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage-path", type=Path, default=Path("/"))
    parser.add_argument("--minimum-cpus", type=int, default=16)
    parser.add_argument("--minimum-memory-gib", type=float, default=32.0)
    parser.add_argument("--minimum-disk-gib", type=float, default=250.0)
    parser.add_argument("--recommended-cpus", type=int, default=32)
    parser.add_argument("--recommended-memory-gib", type=float, default=64.0)
    parser.add_argument("--recommended-disk-gib", type=float, default=500.0)
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--network-timeout", type=float, default=15.0)
    parser.add_argument("--network-attempts", type=int, default=4)
    parser.add_argument("--network-backoff-seconds", type=float, default=2.0)
    parser.add_argument("--allow-user-install", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.network_timeout <= 0:
        parser.error("--network-timeout must be positive")
    if not 1 <= args.network_attempts <= 20:
        parser.error("--network-attempts must be from 1 through 20")
    if not 0 <= args.network_backoff_seconds <= 900:
        parser.error("--network-backoff-seconds must be from 0 through 900")

    os_release = read_key_values(Path("/etc/os-release"))
    cpu = cpu_facts()
    memory = memory_bytes()
    storage = shutil.disk_usage(args.storage_path.resolve())
    sudo = sudo_facts()
    commands = command_facts()
    systemd_running = Path("/run/systemd/system").is_dir()
    hard_blockers: list[str] = []
    warnings: list[str] = []

    if os_release.get("ID") != "ubuntu":
        hard_blockers.append("operating system is not Ubuntu")
    if os_release.get("VERSION_ID") not in SUPPORTED_UBUNTU:
        hard_blockers.append(
            "Ubuntu release is not in the MATLAB R2026a validated set "
            "(22.04 or 24.04)"
        )
    if platform.machine() not in {"x86_64", "AMD64"}:
        hard_blockers.append("MATLAB deployment requires x86-64")
    if not cpu["avx2"]:
        hard_blockers.append("CPU does not expose AVX2")
    if int(cpu["logical_cpus"]) < args.minimum_cpus:
        hard_blockers.append(
            f"only {cpu['logical_cpus']} logical CPUs; "
            f"{args.minimum_cpus} required"
        )
    if memory is None:
        hard_blockers.append("total memory could not be measured")
    elif memory < int(args.minimum_memory_gib * 1024**3):
        hard_blockers.append(
            f"only {memory / 1024**3:.1f} GiB RAM; "
            f"{args.minimum_memory_gib:.1f} GiB required"
        )
    if storage.free < int(args.minimum_disk_gib * 1024**3):
        hard_blockers.append(
            f"only {storage.free / 1024**3:.1f} GiB free at "
            f"{args.storage_path}; {args.minimum_disk_gib:.1f} GiB required"
        )
    if not systemd_running and not args.allow_user_install:
        hard_blockers.append("systemd is not running")
    if not sudo["passwordless"] and not args.allow_user_install:
        hard_blockers.append(
            "root or passwordless sudo is required for unattended boot setup"
        )
    missing_commands = [
        name for name, location in commands.items() if location is None
    ]
    if missing_commands and not sudo["passwordless"]:
        hard_blockers.append(
            "required commands are missing and cannot be installed unattended: "
            + ", ".join(missing_commands)
        )
    elif missing_commands:
        warnings.append(
            "bootstrap will install missing commands: "
            + ", ".join(missing_commands)
        )
    if int(cpu["logical_cpus"]) < args.recommended_cpus:
        warnings.append(
            f"{args.recommended_cpus} logical CPUs are recommended"
        )
    if (
        memory is not None
        and memory < int(args.recommended_memory_gib * 1024**3)
    ):
        warnings.append(
            f"{args.recommended_memory_gib:.1f} GiB RAM is recommended"
        )
    if storage.free < int(args.recommended_disk_gib * 1024**3):
        warnings.append(
            f"{args.recommended_disk_gib:.1f} GiB free NVMe is recommended"
        )

    network = (
        network_facts(
            args.network_timeout,
            attempts=args.network_attempts,
            initial_backoff_seconds=args.network_backoff_seconds,
        )
        if args.network
        else None
    )
    failed_network: list[str] = []
    if isinstance(network, dict):
        failed_network = [
            name
            for name, result in network.items()
            if not result.get("ok")
        ]
        if failed_network:
            hard_blockers.append(
                "outbound HTTPS failed for: " + ", ".join(failed_network)
            )

    failure_class = classify_failure(hard_blockers, failed_network)
    report = {
        "schema": 1,
        "checked_at": utc_now(),
        "host": {
            "hostname": socket.gethostname(),
            "architecture": platform.machine(),
            "kernel": platform.release(),
            "ubuntu": {
                "id": os_release.get("ID"),
                "version_id": os_release.get("VERSION_ID"),
                "pretty_name": os_release.get("PRETTY_NAME"),
            },
        },
        "cpu": cpu,
        "memory": {
            "total_bytes": memory,
            "total_gib": None if memory is None else memory / 1024**3,
        },
        "storage": {
            "path": str(args.storage_path.resolve()),
            "total_bytes": storage.total,
            "used_bytes": storage.used,
            "free_bytes": storage.free,
            "free_gib": storage.free / 1024**3,
        },
        "privilege": sudo,
        "systemd_running": systemd_running,
        "commands": commands,
        "network": network,
        "thresholds": {
            "minimum": {
                "logical_cpus": args.minimum_cpus,
                "memory_gib": args.minimum_memory_gib,
                "free_disk_gib": args.minimum_disk_gib,
            },
            "recommended": {
                "logical_cpus": args.recommended_cpus,
                "memory_gib": args.recommended_memory_gib,
                "free_disk_gib": args.recommended_disk_gib,
            },
        },
        "hard_blockers": hard_blockers,
        "warnings": warnings,
        "failure_class": failure_class,
        "ready": not hard_blockers,
    }
    encoded = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    print(encoded)
    if args.output is not None:
        atomic_json(args.output.resolve(), report)
    if report["ready"]:
        return 0
    return 3 if failure_class == "transient_network" else 2


if __name__ == "__main__":
    raise SystemExit(main())
