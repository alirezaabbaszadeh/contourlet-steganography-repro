"""Hashes and environment metadata for auditable experiment runs."""

from __future__ import annotations

import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any, Mapping

import numpy as np
from numpy.typing import ArrayLike


def canonical_json_bytes(payload: object) -> bytes:
    """Serialize JSON-compatible data deterministically."""

    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_json(payload: object) -> str:
    return sha256_bytes(canonical_json_bytes(payload))


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_array(image: ArrayLike) -> str:
    """Hash an array with an explicit dtype, shape, and byte-order contract."""

    values = np.ascontiguousarray(np.asarray(image, dtype="<f8"))
    digest = hashlib.sha256()
    digest.update(b"ctsteg-array-v1\0")
    digest.update(canonical_json_bytes({"dtype": "<f8", "shape": values.shape}))
    digest.update(b"\0")
    digest.update(values.tobytes(order="C"))
    return digest.hexdigest()


def _git(command: list[str], cwd: Path) -> str | None:
    try:
        process = subprocess.run(
            ["git", "-C", str(cwd), *command],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if process.returncode:
        return None
    return process.stdout.strip()


def git_state(cwd: str | Path | None = None) -> dict[str, object]:
    """Capture the current commit and whether tracked/untracked files differ."""

    location = Path(cwd or Path.cwd()).resolve()
    root = _git(["rev-parse", "--show-toplevel"], location)
    if root is None:
        return {"available": False, "commit": None, "dirty": None}
    repository = Path(root)
    status = _git(["status", "--porcelain=v1", "--untracked-files=normal"], repository)
    return {
        "available": True,
        "commit": _git(["rev-parse", "HEAD"], repository),
        "branch": _git(["branch", "--show-current"], repository),
        "dirty": bool(status),
        "root_name": repository.name,
    }


def _distribution_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def environment_snapshot() -> dict[str, object]:
    """Return portable runtime facts needed to interpret measurements."""

    distributions = [
        "contourlet-steganography-repro",
        "numpy",
        "scipy",
        "Pillow",
        "matplotlib",
    ]
    return {
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": Path(sys.executable).name,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor() or None,
            "cpu_count": os.cpu_count(),
        },
        "dependencies": {
            name: _distribution_version(name) for name in distributions
        },
        "thread_environment": {
            name: os.environ.get(name)
            for name in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
    }


def run_identifier(
    *,
    manifest_sha256: str,
    input_files_sha256: str,
    config_sha256: str,
    evaluation_code_sha256: str,
    method: str,
    method_version: str,
    method_implementation_sha256: str | None,
    options: Mapping[str, Any],
) -> str:
    """Build a stable identifier from scientific inputs, not wall-clock time."""

    digest = sha256_json(
        {
            "schema": 1,
            "manifest_sha256": manifest_sha256,
            "input_files_sha256": input_files_sha256,
            "config_sha256": config_sha256,
            "evaluation_code_sha256": evaluation_code_sha256,
            "method": method,
            "method_version": method_version,
            "method_implementation_sha256": method_implementation_sha256,
            "options": dict(options),
        }
    )
    return digest[:16]
