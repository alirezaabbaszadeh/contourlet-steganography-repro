from __future__ import annotations

from dataclasses import dataclass
import re


COMMANDS = {
    "health_check",
    "runtime_check",
    "bootstrap_check",
    "worker_benchmark",
    "research_status",
    "run_final_5j",
}
REPOSITORY = "alirezaabbaszadeh/contourlet-steganography-repro"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class RequestError(ValueError):
    pass


@dataclass(frozen=True)
class ControlRequest:
    command: str
    scientific_repository: str
    scientific_commit: str
    workers: int | None = None


def parse_request(payload: dict) -> ControlRequest:
    if payload.get("schema_version") != 1:
        raise RequestError("schema_version must be 1")

    command = payload.get("command")
    if command not in COMMANDS:
        raise RequestError("unknown command")

    repository = payload.get("scientific_repository")
    if repository != REPOSITORY:
        raise RequestError("unexpected scientific repository")

    commit = payload.get("scientific_commit")
    if not isinstance(commit, str) or not SHA_RE.fullmatch(commit):
        raise RequestError("scientific_commit must be a 40-character hexadecimal SHA")

    allowed = {
        "schema_version",
        "command",
        "scientific_repository",
        "scientific_commit",
    }
    workers = None
    if command == "worker_benchmark":
        allowed.add("workers")
        workers = payload.get("workers")
        if not isinstance(workers, int) or isinstance(workers, bool) or workers < 1:
            raise RequestError("workers must be a positive integer")
        if workers > 44:
            raise RequestError("maximum worker count is 44")

    unknown = set(payload) - allowed
    if unknown:
        raise RequestError(f"unknown fields: {sorted(unknown)}")

    return ControlRequest(command, repository, commit, workers)
