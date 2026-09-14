from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Sequence

from control.run_request import RequestRunError, resolve_request_path, run_request


GIT_TIMEOUT_SECONDS = 60


class HeadRequestError(ValueError):
    pass


def changed_request_paths(repo_root: Path, commit: str = "HEAD") -> list[str]:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-only",
            "-r",
            "-z",
            commit,
            "--",
            "requests/",
        ],
        check=False,
        shell=False,
        timeout=GIT_TIMEOUT_SECONDS,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise HeadRequestError(f"git diff-tree failed with exit code {completed.returncode}")

    decoded: list[str] = []
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            path = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HeadRequestError("git reported a non-UTF-8 request path") from exc
        posix = PurePosixPath(path)
        if (
            len(posix.parts) == 2
            and posix.parts[0] == "requests"
            and posix.suffix.lower() == ".json"
            and posix.name not in {".", ".."}
        ):
            decoded.append(path)

    if len(decoded) != 1:
        raise HeadRequestError(
            f"head commit must change exactly one requests/*.json file; found {len(decoded)}"
        )
    return decoded


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the single server-control request changed by HEAD.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--commit", default="HEAD")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    paths = changed_request_paths(args.repo_root, args.commit)
    request_path = resolve_request_path(args.repo_root, paths[0])
    return run_request(request_path)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HeadRequestError, RequestRunError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"server control head request failed: {exc}", file=sys.stderr)
        raise SystemExit(64)
