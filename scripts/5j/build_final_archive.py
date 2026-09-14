#!/usr/bin/env python3
"""Build one deterministic FINAL-5J archive after local project completion.

This command is post-run only. It packages explicitly declared roots, rejects
symlinks and common plaintext-secret patterns, writes an internal SHA-256
inventory, and emits an external manifest beside the final tar.gz archive.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tarfile
import tempfile
from typing import Any, Iterable


PROTOCOL_ID = "FINAL-5J-v1"
SECRET_NAME = re.compile(
    r"(^|[._-])(id_rsa|id_ed25519|private[_-]?key|secret|token|password|credential|license[_-]?key)([._-]|$)",
    re.IGNORECASE,
)
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks"}
_PRIVATE_HEADER_PREFIX = b"-----BEGIN "
_PRIVATE_HEADER_SUFFIX = b"PRIVATE KEY-----"
SECRET_TEXT_PATTERNS = tuple(
    _PRIVATE_HEADER_PREFIX + middle + _PRIVATE_HEADER_SUFFIX
    for middle in (b"RSA ", b"OPENSSH ", b"")
) + (
    b"gh" + b"p_",
    b"github_" + b"pat_",
)


class FinalArchiveError(ValueError):
    """Raised when final archival safety or completeness checks fail."""


def archive_timestamp() -> str:
    """Return deterministic manifest time from SOURCE_DATE_EPOCH (default 0)."""
    raw = os.environ.get("SOURCE_DATE_EPOCH", "0")
    try:
        seconds = int(raw)
    except ValueError as error:
        raise FinalArchiveError("SOURCE_DATE_EPOCH must be an integer") from error
    if seconds < 0:
        raise FinalArchiveError("SOURCE_DATE_EPOCH must be nonnegative")
    return datetime.fromtimestamp(
        seconds,
        tz=timezone.utc,
    ).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def parse_include(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--include must use NAME=PATH")
    name, raw_path = value.split("=", 1)
    name = name.strip()
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise argparse.ArgumentTypeError(
            "include NAME must be a safe path segment"
        )
    path = Path(raw_path).expanduser().resolve()
    if not path.exists() or path.is_symlink():
        raise argparse.ArgumentTypeError(f"include path is invalid: {path}")
    return name, path


def iter_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise FinalArchiveError(f"symlink is prohibited: {path}")
        if path.is_file():
            yield path


def archive_path(name: str, root: Path, path: Path) -> str:
    relative = (
        path.name if root.is_file() else path.relative_to(root).as_posix()
    )
    return f"inputs/{name}/{relative}"


def scan_secret(path: Path) -> None:
    lowered = path.name.lower()
    if path.suffix.lower() in SECRET_SUFFIXES or SECRET_NAME.search(lowered):
        raise FinalArchiveError(f"possible plaintext secret filename: {path}")
    if path.stat().st_size > 16 * 1024 * 1024:
        return
    payload = path.read_bytes()
    for pattern in SECRET_TEXT_PATTERNS:
        if pattern in payload:
            raise FinalArchiveError(
                f"possible plaintext secret pattern in {path}: {pattern!r}"
            )


def tar_info(name: str, size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name=name)
    info.size = size
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = 0o644
    return info


def add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    archive.addfile(tar_info(name, len(payload)), io.BytesIO(payload))


def add_file(archive: tarfile.TarFile, name: str, path: Path) -> None:
    with path.open("rb") as stream:
        archive.addfile(tar_info(name, path.stat().st_size), stream)


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(
            payload,
            stream,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include",
        action="append",
        type=parse_include,
        required=True,
        help="Explicit final root in NAME=PATH form; repeat as needed.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--plan-id", required=True)
    parser.add_argument(
        "--classification",
        choices=("public", "restricted_encrypted_destination"),
        required=True,
    )
    parser.add_argument(
        "--allow-incomplete-marker",
        action="store_true",
        help="Only for diagnostic archives; final project archives omit this.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        output = args.output.resolve()
        if output.suffixes[-2:] != [".tar", ".gz"]:
            raise FinalArchiveError("output filename must end in .tar.gz")
        include_names = [name for name, _ in args.include]
        if len(include_names) != len(set(include_names)):
            raise FinalArchiveError("include names must be unique")
        entries: list[dict[str, Any]] = []
        sources: dict[str, Path] = {}
        for name, root in args.include:
            for path in iter_files(root):
                scan_secret(path)
                member = archive_path(name, root, path)
                if member in sources:
                    raise FinalArchiveError(
                        f"duplicate archive member: {member}"
                    )
                sources[member] = path
                entries.append(
                    {
                        "path": member,
                        "size": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                )
        if not entries:
            raise FinalArchiveError(
                "no files were selected for the final archive"
            )
        entries.sort(key=lambda item: item["path"])
        manifest = {
            "schema_version": 1,
            "protocol_id": PROTOCOL_ID,
            "run_id": args.run_id,
            "plan_id": args.plan_id,
            "classification": args.classification,
            "backup_policy": "final_only_after_run_completion",
            "diagnostic_incomplete": bool(args.allow_incomplete_marker),
            "created_at": archive_timestamp(),
            "file_count": len(entries),
            "byte_count": sum(int(item["size"]) for item in entries),
            "files": entries,
        }
        manifest["inventory_sha256"] = hashlib.sha256(
            canonical_json_bytes(manifest)
        ).hexdigest()
        manifest_bytes = (
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")

        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_stream:
            temporary = Path(temporary_stream.name)
        try:
            with temporary.open("wb") as raw_stream:
                with gzip.GzipFile(
                    filename="",
                    mode="wb",
                    fileobj=raw_stream,
                    mtime=0,
                ) as gzip_stream:
                    with tarfile.open(
                        fileobj=gzip_stream,
                        mode="w|",
                        format=tarfile.PAX_FORMAT,
                    ) as archive:
                        add_bytes(
                            archive,
                            "FINAL_ARCHIVE_MANIFEST.json",
                            manifest_bytes,
                        )
                        for entry in entries:
                            add_file(
                                archive,
                                str(entry["path"]),
                                sources[str(entry["path"])],
                            )
                raw_stream.flush()
                os.fsync(raw_stream.fileno())
            os.replace(temporary, output)
        finally:
            if temporary.exists():
                temporary.unlink()
        external = {
            **manifest,
            "archive": str(output),
            "archive_size": output.stat().st_size,
            "archive_sha256": sha256_file(output),
            "verification_status": "not_yet_verified",
        }
        atomic_json(
            output.with_suffix(output.suffix + ".manifest.json"),
            external,
        )
    except (FinalArchiveError, OSError, ValueError) as error:
        print(
            f"FINAL-5J final archive build failed: {error}",
            file=sys.stderr,
        )
        return 1

    print(json.dumps(external, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
