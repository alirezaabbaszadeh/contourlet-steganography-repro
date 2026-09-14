#!/usr/bin/env python3
"""Download the 108 outcome-blind selected COCO val2017 source images via S3.

The COCO custom hostname currently presents a TLS hostname mismatch on some
hosted runners. This downloader does not disable certificate validation. It
uses the same public ``images.cocodataset.org`` bucket through Amazon S3's
certificate-valid endpoint and reuses the exact eligibility/order functions
from ``prepare_coco_candidates.py``.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import sys
from urllib.request import Request, urlopen


S3_BASE = "https://s3.amazonaws.com/images.cocodataset.org/val2017"


class DownloadError(RuntimeError):
    pass


def load_preparer(root: Path):
    path = root / "scripts/5j/prepare_coco_candidates.py"
    spec = importlib.util.spec_from_file_location("ctsteg_prepare_coco_candidates", path)
    if spec is None or spec.loader is None:
        raise DownloadError(f"cannot load preparation module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fetch(url: str, destination: Path) -> None:
    if destination.is_file() and destination.stat().st_size:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    request = Request(url, headers={"User-Agent": "ctsteg-final-5j/1"})
    try:
        with urlopen(request, timeout=90) as response, temporary.open("wb") as stream:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        if not temporary.stat().st_size:
            raise DownloadError(f"empty source download: {url}")
        os.replace(temporary, destination)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.repository_root.resolve()
    try:
        preparer = load_preparer(root)
        license_by_id, images = preparer.load_coco_metadata(args.annotations.resolve())
        eligible = preparer.eligible_images(license_by_id, images)
        selected = eligible[: preparer.SOURCE_IMAGE_COUNT]
        source_dir = args.source_dir.resolve()
        for index, item in enumerate(selected, start=1):
            file_name = str(item["file_name"])
            url = f"{S3_BASE}/{file_name}"
            fetch(url, source_dir / file_name)
            if index % 20 == 0 or index == len(selected):
                print(f"downloaded {index}/{len(selected)} selected COCO sources")
    except (DownloadError, OSError, ValueError) as error:
        print(f"FINAL-5J selected COCO download failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
