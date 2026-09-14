#!/usr/bin/env python3
"""Prepare at least 54 real FINAL-5J candidate pairs from COCO 2017 val images.

The script is intentionally outcome-blind. It reads the official COCO instance
metadata, keeps only images carrying the Creative Commons Attribution 2.0
license, orders eligible images by a protocol-domain SHA-256 score, takes 108
unique source images, and deterministically pairs the first 54 with the next 54.

For each pair it creates:

* one 512x512 grayscale cover;
* one 128x128 grayscale secret;
* exact SHA-256 provenance for source and derived bytes;
* COCO/Flickr source URLs and the explicit CC BY 2.0 license;
* a candidate CSV accepted by ``freeze_data_manifests.py``;
* a machine-readable preparation report.

No algorithm output is inspected. The scientific split is performed later by
``freeze_data_manifests.py`` so calibration, dry-run, main, and sweep assignment
remains independent of steganography outcomes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping
from urllib.request import Request, urlopen

from PIL import Image, ImageOps


PROTOCOL_ID = "FINAL-5J-v1"
PREPARATION_VERSION = 1
PAIR_COUNT = 54
SOURCE_IMAGE_COUNT = PAIR_COUNT * 2
COCO_DATASET_URL = "https://cocodataset.org/#download"
CC_BY_20_URLS = {
    "http://creativecommons.org/licenses/by/2.0/",
    "https://creativecommons.org/licenses/by/2.0/",
}
CC_BY_20_LABEL = "CC BY 2.0"
PREPROCESSING_ID = "coco2017-val-centerfit-bicubic-pillowL-v1"
CANDIDATE_HEADER = [
    "pair_id",
    "cover",
    "secret",
    "cover_source",
    "secret_source",
    "cover_rights_status",
    "secret_rights_status",
    "cover_license",
    "secret_license",
    "preprocessing_id",
    "redistribution_allowed",
    "private_archive_object_id",
    "notes",
]


class CocoPreparationError(ValueError):
    """Raised when COCO candidates cannot be prepared reproducibly."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(payload: object) -> str:
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    return sha256_bytes(encoded)


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def atomic_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CANDIDATE_HEADER)
        writer.writeheader()
        writer.writerows(rows)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def load_coco_metadata(path: Path) -> tuple[dict[int, Mapping[str, Any]], list[Mapping[str, Any]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CocoPreparationError(f"COCO annotation JSON is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise CocoPreparationError(f"invalid COCO JSON: {error}") from error
    licenses = payload.get("licenses")
    images = payload.get("images")
    if not isinstance(licenses, list) or not isinstance(images, list):
        raise CocoPreparationError("COCO JSON must contain licenses and images arrays")
    license_by_id: dict[int, Mapping[str, Any]] = {}
    for item in licenses:
        if not isinstance(item, Mapping) or not isinstance(item.get("id"), int):
            raise CocoPreparationError("invalid COCO license record")
        license_by_id[int(item["id"])] = item
    return license_by_id, [item for item in images if isinstance(item, Mapping)]


def eligible_images(
    license_by_id: Mapping[int, Mapping[str, Any]],
    images: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    seen_names: set[str] = set()
    for item in images:
        image_id = item.get("id")
        license_id = item.get("license")
        file_name = str(item.get("file_name", "")).strip()
        if not isinstance(image_id, int) or not isinstance(license_id, int) or not file_name:
            continue
        license_record = license_by_id.get(license_id)
        if not isinstance(license_record, Mapping):
            continue
        license_url = str(license_record.get("url", "")).strip()
        if license_url not in CC_BY_20_URLS:
            continue
        width = item.get("width")
        height = item.get("height")
        if not isinstance(width, int) or not isinstance(height, int) or min(width, height) < 256:
            continue
        coco_url = str(item.get("coco_url", "")).strip()
        flickr_url = str(item.get("flickr_url", "")).strip()
        if not coco_url:
            continue
        if image_id in seen_ids or file_name in seen_names:
            raise CocoPreparationError("duplicate COCO image identity in metadata")
        seen_ids.add(image_id)
        seen_names.add(file_name)
        score = hashlib.sha256(
            f"{PROTOCOL_ID}:{PREPARATION_VERSION}:coco-source:{image_id}:{file_name}".encode("utf-8")
        ).hexdigest()
        eligible.append(
            {
                "id": image_id,
                "license_id": license_id,
                "license_name": str(license_record.get("name", "")).strip(),
                "license_url": license_url,
                "file_name": file_name,
                "width": width,
                "height": height,
                "coco_url": coco_url,
                "flickr_url": flickr_url,
                "date_captured": str(item.get("date_captured", "")).strip(),
                "selection_score": score,
            }
        )
    eligible.sort(key=lambda item: (item["selection_score"], item["id"]))
    if len(eligible) < SOURCE_IMAGE_COUNT:
        raise CocoPreparationError(
            f"need at least {SOURCE_IMAGE_COUNT} CC BY 2.0 COCO images; found {len(eligible)}"
        )
    return eligible


def download_if_missing(item: Mapping[str, Any], source_dir: Path) -> Path:
    destination = source_dir / str(item["file_name"])
    if destination.is_file():
        return destination
    source_dir.mkdir(parents=True, exist_ok=True)
    request = Request(str(item["coco_url"]), headers={"User-Agent": "ctsteg-final-5j/1"})
    try:
        with urlopen(request, timeout=60) as response:
            payload = response.read()
    except OSError as error:
        raise CocoPreparationError(
            f"failed to download COCO image {item['id']}: {error}"
        ) from error
    if not payload:
        raise CocoPreparationError(f"empty COCO image download: {item['id']}")
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, destination)
    return destination


def center_fit_grayscale(source: Path, destination: Path, *, size: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(source) as image:
            image.load()
            converted = image.convert("L")
            fitted = ImageOps.fit(
                converted,
                (size, size),
                method=Image.Resampling.BICUBIC,
                centering=(0.5, 0.5),
            )
            temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
            fitted.save(temporary, format="PNG", optimize=False, compress_level=9)
            os.replace(temporary, destination)
    except (OSError, ValueError) as error:
        raise CocoPreparationError(f"cannot preprocess {source}: {error}") from error


def source_label(item: Mapping[str, Any]) -> str:
    return f"COCO 2017 val image {item['id']} | {item['coco_url']} | Flickr {item['flickr_url']}"


def pair_rows(
    selected: list[dict[str, Any]],
    *,
    source_dir: Path,
    output_dir: Path,
    download: bool,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    covers = selected[:PAIR_COUNT]
    secrets = selected[PAIR_COUNT:SOURCE_IMAGE_COUNT]
    rows: list[dict[str, str]] = []
    provenance: list[dict[str, Any]] = []
    used_source_ids: set[int] = set()
    for index, (cover_item, secret_item) in enumerate(zip(covers, secrets, strict=True), start=1):
        if int(cover_item["id"]) == int(secret_item["id"]):
            raise CocoPreparationError("cover and secret source identities overlap")
        for item in (cover_item, secret_item):
            source_id = int(item["id"])
            if source_id in used_source_ids:
                raise CocoPreparationError("a COCO source image is reused across candidate roles")
            used_source_ids.add(source_id)
        cover_source_path = source_dir / str(cover_item["file_name"])
        secret_source_path = source_dir / str(secret_item["file_name"])
        if download:
            cover_source_path = download_if_missing(cover_item, source_dir)
            secret_source_path = download_if_missing(secret_item, source_dir)
        for role, path in (("cover", cover_source_path), ("secret", secret_source_path)):
            if not path.is_file():
                raise CocoPreparationError(
                    f"{role} source file missing; rerun with --download or provide COCO val2017 files: {path}"
                )
        pair_id = f"coco-{int(cover_item['id']):012d}-{int(secret_item['id']):012d}"
        cover_out = output_dir / "covers" / f"{pair_id}.png"
        secret_out = output_dir / "secrets" / f"{pair_id}.png"
        center_fit_grayscale(cover_source_path, cover_out, size=512)
        center_fit_grayscale(secret_source_path, secret_out, size=128)
        cover_source_sha = sha256_file(cover_source_path)
        secret_source_sha = sha256_file(secret_source_path)
        cover_derived_sha = sha256_file(cover_out)
        secret_derived_sha = sha256_file(secret_out)
        rows.append(
            {
                "pair_id": pair_id,
                "cover": os.path.relpath(cover_out, output_dir),
                "secret": os.path.relpath(secret_out, output_dir),
                "cover_source": source_label(cover_item),
                "secret_source": source_label(secret_item),
                "cover_rights_status": "redistribution_permitted",
                "secret_rights_status": "redistribution_permitted",
                "cover_license": f"{CC_BY_20_LABEL} {cover_item['license_url']}",
                "secret_license": f"{CC_BY_20_LABEL} {secret_item['license_url']}",
                "preprocessing_id": PREPROCESSING_ID,
                "redistribution_allowed": "true",
                "private_archive_object_id": "",
                "notes": (
                    f"COCO source SHA256 cover={cover_source_sha} secret={secret_source_sha}; "
                    "deterministic center-fit, Pillow L conversion, bicubic resize"
                ),
            }
        )
        provenance.append(
            {
                "pair_id": pair_id,
                "cover": {
                    **cover_item,
                    "source_path": str(cover_source_path.resolve()),
                    "source_sha256": cover_source_sha,
                    "derived_path": str(cover_out.resolve()),
                    "derived_sha256": cover_derived_sha,
                },
                "secret": {
                    **secret_item,
                    "source_path": str(secret_source_path.resolve()),
                    "source_sha256": secret_source_sha,
                    "derived_path": str(secret_out.resolve()),
                    "derived_sha256": secret_derived_sha,
                },
            }
        )
    if len(rows) != PAIR_COUNT or len(used_source_ids) != SOURCE_IMAGE_COUNT:
        raise CocoPreparationError("candidate pair/source cardinality invariant failed")
    return rows, provenance


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, required=True, help="COCO instances_val2017.json")
    parser.add_argument("--source-dir", type=Path, required=True, help="COCO val2017 image directory")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "data/5j/coco_candidates",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=root / "data/5j/coco_candidates/candidate_pairs.csv",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=root / "data/5j/coco_candidates/preparation_report.json",
    )
    parser.add_argument("--download", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        annotation_path = args.annotations.resolve()
        source_dir = args.source_dir.resolve()
        output_dir = args.output_dir.resolve()
        license_by_id, images = load_coco_metadata(annotation_path)
        eligible = eligible_images(license_by_id, images)
        selected = eligible[:SOURCE_IMAGE_COUNT]
        rows, provenance = pair_rows(
            selected,
            source_dir=source_dir,
            output_dir=output_dir,
            download=bool(args.download),
        )
        catalog = args.catalog.resolve()
        atomic_csv(catalog, rows)
        report = {
            "schema_version": 1,
            "protocol_id": PROTOCOL_ID,
            "preparation_version": PREPARATION_VERSION,
            "dataset": "COCO 2017 validation",
            "dataset_url": COCO_DATASET_URL,
            "annotation_file": str(annotation_path),
            "annotation_sha256": sha256_file(annotation_path),
            "license_policy": {
                "allowed": [CC_BY_20_LABEL],
                "allowed_urls": sorted(CC_BY_20_URLS),
                "rights_status": "redistribution_permitted",
            },
            "selection_rule": (
                "filter CC BY 2.0 and minimum dimension 256; order by SHA-256 of "
                "protocol/version/image-id/file-name; take first 108; pair positions 0..53 with 54..107"
            ),
            "outcome_blind": True,
            "eligible_count": len(eligible),
            "selected_source_count": len(selected),
            "candidate_pair_count": len(rows),
            "preprocessing_id": PREPROCESSING_ID,
            "catalog": str(catalog),
            "catalog_sha256": sha256_file(catalog),
            "pairs": provenance,
            "report_identity": "",
        }
        report["report_identity"] = sha256_json(
            {key: value for key, value in report.items() if key != "report_identity"}
        )
        atomic_json(args.report.resolve(), report)
    except (CocoPreparationError, OSError, ValueError) as error:
        print(f"FINAL-5J COCO candidate preparation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
