from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from typing import Sequence

from control.dispatch import build_operation
from control.request import RequestError, parse_request


SCIENTIFIC_URL = "https://github.com/alirezaabbaszadeh/contourlet-steganography-repro.git"
DEFAULT_CHECKOUT = Path("/srv/ctsteg/control/scientific-repo")
GIT_TIMEOUT_SECONDS = 600
OPERATION_TIMEOUT_SECONDS = 14400


class RequestRunError(ValueError):
    pass


def resolve_request_path(repo_root: Path, requested: str) -> Path:
    requests_root = (repo_root / "requests").resolve()
    candidate = (repo_root / requested).resolve()
    try:
        candidate.relative_to(requests_root)
    except ValueError as exc:
        raise RequestRunError("request must stay inside requests directory") from exc
    if candidate.suffix.lower() != ".json":
        raise RequestRunError("request must be a JSON request")
    if not candidate.is_file():
        raise RequestRunError(f"request file is not readable: {candidate}")
    return candidate


def run_process(argv: Sequence[str], *, timeout_seconds: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(argv),
        check=False,
        shell=False,
        timeout=timeout_seconds,
    )


def _run_capture(argv: Sequence[str], *, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        check=False,
        shell=False,
        timeout=timeout_seconds,
        capture_output=True,
        text=True,
    )


def _require_success(completed: subprocess.CompletedProcess, label: str) -> None:
    if completed.returncode != 0:
        raise RequestRunError(f"{label} failed with exit code {completed.returncode}")


def prepare_exact_checkout(commit: str, checkout: Path = DEFAULT_CHECKOUT) -> Path:
    checkout = Path(checkout)
    checkout.parent.mkdir(parents=True, exist_ok=True)

    if not (checkout / ".git").is_dir():
        if checkout.exists() and any(checkout.iterdir()):
            raise RequestRunError(f"scientific checkout is non-empty and not a git repository: {checkout}")
        checkout.mkdir(parents=True, exist_ok=True)
        _require_success(
            run_process(["git", "init", str(checkout)], timeout_seconds=GIT_TIMEOUT_SECONDS),
            "git init",
        )
        _require_success(
            run_process(
                ["git", "-C", str(checkout), "remote", "add", "origin", SCIENTIFIC_URL],
                timeout_seconds=GIT_TIMEOUT_SECONDS,
            ),
            "git remote add",
        )
    else:
        _require_success(
            run_process(
                ["git", "-C", str(checkout), "remote", "set-url", "origin", SCIENTIFIC_URL],
                timeout_seconds=GIT_TIMEOUT_SECONDS,
            ),
            "git remote set-url",
        )

    _require_success(
        run_process(
            ["git", "-C", str(checkout), "fetch", "--no-tags", "--prune", "origin", commit],
            timeout_seconds=GIT_TIMEOUT_SECONDS,
        ),
        "git fetch exact commit",
    )
    _require_success(
        run_process(
            ["git", "-C", str(checkout), "checkout", "--detach", "--force", commit],
            timeout_seconds=GIT_TIMEOUT_SECONDS,
        ),
        "git detached checkout",
    )
    _require_success(
        run_process(
            ["git", "-C", str(checkout), "reset", "--hard", commit],
            timeout_seconds=GIT_TIMEOUT_SECONDS,
        ),
        "git reset exact commit",
    )
    _require_success(
        run_process(
            ["git", "-C", str(checkout), "clean", "-ffdx"],
            timeout_seconds=GIT_TIMEOUT_SECONDS,
        ),
        "git clean",
    )

    head = _run_capture(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        timeout_seconds=GIT_TIMEOUT_SECONDS,
    )
    _require_success(head, "git rev-parse HEAD")
    if head.stdout.strip() != commit:
        raise RequestRunError(
            f"scientific checkout SHA mismatch: expected {commit}, found {head.stdout.strip()}"
        )
    return checkout


def _load_request(path: Path):
    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RequestRunError(f"invalid JSON request: {exc}") from exc
    if not isinstance(payload, dict):
        raise RequestRunError("JSON request must be an object")
    return raw, parse_request(payload)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_request(request_path: Path) -> int:
    raw, request = _load_request(request_path)
    started_at = _now()

    if request.command == "health_check":
        checkout = DEFAULT_CHECKOUT
    else:
        checkout = prepare_exact_checkout(request.scientific_commit)

    operation_argv = build_operation(request, str(checkout))
    completed = run_process(operation_argv, timeout_seconds=OPERATION_TIMEOUT_SECONDS)
    finished_at = _now()
    summary = {
        "schema_version": 1,
        "request_sha256": hashlib.sha256(raw).hexdigest(),
        "command": request.command,
        "scientific_commit": request.scientific_commit,
        "hostname": socket.gethostname(),
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_code": int(completed.returncode),
    }
    print(json.dumps(summary, sort_keys=True))
    return int(completed.returncode)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute one validated server-control request.")
    parser.add_argument("request_path", help="Tracked JSON file under requests/")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    request_path = resolve_request_path(args.repo_root, args.request_path)
    return run_request(request_path)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RequestRunError, RequestError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"server control request failed: {exc}", file=sys.stderr)
        raise SystemExit(64)
