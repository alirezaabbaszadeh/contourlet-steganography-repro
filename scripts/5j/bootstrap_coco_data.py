#!/usr/bin/env python3
"""Bootstrap the real FINAL-5J data manifests from COCO 2017 validation.

This operator command performs only data acquisition and deterministic
preprocessing; it never runs a steganography method or inspects scientific
outcomes.

Steps:
1. download the official COCO train/val annotation archive if needed;
2. extract only ``annotations/instances_val2017.json``;
3. run ``prepare_coco_candidates.py --download`` to fetch the 108 selected
   CC BY 2.0 validation images and create 54 preprocessed candidate pairs;
4. run ``freeze_data_manifests.py`` to create calibration, dry-run, main-50,
   and sweep-10 manifests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import Request, urlopen
import zipfile


ANNOTATIONS_URL = (
    "https://images.cocodataset.org/annotations/annotations_trainval2017.zip"
)
ANNOTATION_MEMBER = "annotations/instances_val2017.json"


class BootstrapDataError(RuntimeError):
    """Raised when the COCO bootstrap cannot complete safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    if destination.is_file() and destination.stat().st_size:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    request = Request(url, headers={"User-Agent": "ctsteg-final-5j/1"})
    try:
        with urlopen(request, timeout=120) as response, temporary.open("wb") as stream:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        if not temporary.stat().st_size:
            raise BootstrapDataError("downloaded annotation archive is empty")
        os.replace(temporary, destination)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def extract_annotation(archive: Path, destination: Path) -> None:
    if destination.is_file() and destination.stat().st_size:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as bundle:
            names = set(bundle.namelist())
            if ANNOTATION_MEMBER not in names:
                raise BootstrapDataError(
                    f"COCO archive lacks {ANNOTATION_MEMBER}"
                )
            payload = bundle.read(ANNOTATION_MEMBER)
    except (OSError, zipfile.BadZipFile) as error:
        raise BootstrapDataError(f"invalid COCO annotation archive: {error}") from error
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, destination)


def run_checked(command: list[str], *, cwd: Path) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise BootstrapDataError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{result.stdout}"
        )
    return result.stdout


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=root / "data/5j/coco2017",
    )
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=root / "data-manifests/5j",
    )
    parser.add_argument(
        "--annotations-url",
        default=ANNOTATIONS_URL,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    workspace = args.workspace.resolve()
    manifest_dir = args.manifest_dir.resolve()
    archive = workspace / "annotations_trainval2017.zip"
    annotation_json = workspace / "annotations" / "instances_val2017.json"
    source_dir = workspace / "val2017"
    candidate_dir = workspace / "prepared"
    catalog = candidate_dir / "candidate_pairs.csv"
    preparation_report = candidate_dir / "preparation_report.json"
    freeze_report = manifest_dir / "data_freeze_report.json"
    try:
        download(str(args.annotations_url), archive)
        extract_annotation(archive, annotation_json)
        preparation_output = run_checked(
            [
                sys.executable,
                str(root / "scripts/5j/prepare_coco_candidates.py"),
                "--annotations",
                str(annotation_json),
                "--source-dir",
                str(source_dir),
                "--output-dir",
                str(candidate_dir),
                "--catalog",
                str(catalog),
                "--report",
                str(preparation_report),
                "--download",
            ],
            cwd=root,
        )
        freeze_output = run_checked(
            [
                sys.executable,
                str(root / "scripts/5j/freeze_data_manifests.py"),
                "--catalog",
                str(catalog),
                "--output-dir",
                str(manifest_dir),
                "--report",
                str(freeze_report),
            ],
            cwd=root,
        )
        report = {
            "schema_version": 1,
            "protocol_id": "FINAL-5J-v1",
            "source": "COCO 2017 validation",
            "annotations_url": str(args.annotations_url),
            "annotation_archive_sha256": sha256_file(archive),
            "instances_val2017_sha256": sha256_file(annotation_json),
            "candidate_catalog": str(catalog),
            "candidate_catalog_sha256": sha256_file(catalog),
            "preparation_report": str(preparation_report),
            "preparation_report_sha256": sha256_file(preparation_report),
            "freeze_report": str(freeze_report),
            "freeze_report_sha256": sha256_file(freeze_report),
            "manifest_dir": str(manifest_dir),
            "outcome_blind": True,
            "preparation_stdout": preparation_output,
            "freeze_stdout": freeze_output,
        }
    except (BootstrapDataError, OSError, ValueError) as error:
        print(f"FINAL-5J COCO bootstrap failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
