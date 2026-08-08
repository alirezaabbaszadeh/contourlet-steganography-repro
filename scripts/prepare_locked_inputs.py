#!/usr/bin/env python3
"""Acquire and freeze the bounded DIGITAL_A_D input set.

The script deliberately uses the USC-SIPI origin and Wikimedia Commons'
MediaWiki API directly.  It does not use an image proxy, optimizer, or CDN
other than the ``thumburl`` returned by Wikimedia for the requested revision.

Existing files are never replaced by default.  ``--resume`` reuses only
verified, byte-identical locked files.  ``--overwrite`` is the only mode that
permits replacement.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date
import hashlib
from html import unescape
from http.client import HTTPException
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import uuid

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from ctsteg.digital_ad.preprocessing import load_uint8_grayscale
from ctsteg.provenance import sha256_array, sha256_file


LOCK_SCHEMA = 2
LOCK_NAME = "DIGITAL_A_D-input-lock-v2"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
COMMONS_THUMB_WIDTH = 1600
USC_CATALOGUE_URL = (
    "https://sipi.usc.edu/database/database.php?volume=misc"
)
USC_CHECKSUM_URL = "https://sipi.usc.edu/database/checksums.php"
USC_RIGHTS_URL = "https://sipi.usc.edu/database/copyright.php"
USER_AGENT = (
    "ctsteg-reproduction/0.5 "
    "(research input lock; "
    "https://github.com/alirezaabbaszadeh/"
    "contourlet-steganography-repro)"
)
RETRYABLE_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}
ALLOWED_LICENSE_SHORT_NAMES = {
    "Public domain",
    "CC0",
    "CC BY 1.0",
    "CC BY 2.0",
    "CC BY 2.5",
    "CC BY 3.0",
    "CC BY 4.0",
    "CC BY-SA 1.0",
    "CC BY-SA 2.0",
    "CC BY-SA 2.5",
    "CC BY-SA 3.0",
    "CC BY-SA 4.0",
}


class LockConflict(RuntimeError):
    """An existing locked file does not match the requested acquisition."""


@dataclass(frozen=True)
class UscAsset:
    asset_id: str
    identifier: str
    filename: str
    official_posix_cksum: int
    stratum: str
    rights: str

    @property
    def source_path(self) -> str:
        return f"misc/{self.identifier}.tiff"

    @property
    def download_url(self) -> str:
        return (
            "https://sipi.usc.edu/database/download.php?"
            + urlencode({"img": self.identifier, "vol": "misc"})
        )


@dataclass(frozen=True)
class CommonsAsset:
    asset_id: str
    title: str
    filename: str
    stratum: str


@dataclass(frozen=True)
class PairSpec:
    pair_id: str
    cover_asset_id: str
    secret_asset_id: str
    split: str


USC_ASSETS: tuple[UscAsset, ...] = (
    UscAsset(
        "cover-baboon",
        "4.2.03",
        "baboon.tiff",
        3944512653,
        "traceability_core",
        (
            "USC-SIPI research database; scan from a magazine picture; "
            "copyright belongs to the original publisher or photographer; "
            "not redistributed by this repository"
        ),
    ),
    UscAsset(
        "cover-boat",
        "boat.512",
        "boat.tiff",
        2515944092,
        "traceability_core",
        (
            "USC-SIPI research database; source and copyright status unknown; "
            "not redistributed by this repository"
        ),
    ),
    UscAsset(
        "cover-peppers",
        "4.2.07",
        "peppers.tiff",
        2608899817,
        "traceability_core",
        (
            "USC-SIPI research database; source and copyright status unknown; "
            "not redistributed by this repository"
        ),
    ),
    UscAsset(
        "cover-house",
        "house",
        "house.tiff",
        3014996685,
        "traceability_core",
        (
            "USC-SIPI research database; source and copyright status unknown; "
            "not redistributed by this repository"
        ),
    ),
    UscAsset(
        "cover-usc-4.1.07-calibration",
        "4.1.07",
        "usc-4.1.07.tiff",
        2545388887,
        "calibration",
        (
            "USC-SIPI photograph of jelly beans taken at USC; USC-SIPI "
            "copyright page marks it free to use; calibration only"
        ),
    ),
    UscAsset(
        "cover-usc-4.1.08-calibration",
        "4.1.08",
        "usc-4.1.08.tiff",
        4286241145,
        "calibration",
        (
            "USC-SIPI photograph of jelly beans taken at USC; USC-SIPI "
            "copyright page marks it free to use; calibration only"
        ),
    ),
)


COMMONS_ASSETS: tuple[CommonsAsset, ...] = (
    CommonsAsset(
        "secret-water-lilies",
        (
            "File:Claude Monet - Water Lilies - 1933.1157 - "
            "Art Institute of Chicago.jpg"
        ),
        "water-lilies.jpg",
        "traceability_core",
    ),
    CommonsAsset(
        "secret-great-wave",
        (
            "File:The Great Wave off Kanagawa LACMA M.81.91.2 "
            "(1 of 2).jpg"
        ),
        "great-wave.jpg",
        "traceability_core",
    ),
    CommonsAsset(
        "secret-grande-jatte",
        "File:A Sunday on La Grande Jatte, Georges Seurat, 1884.jpg",
        "grande-jatte.jpg",
        "traceability_core",
    ),
    CommonsAsset(
        "secret-bedroom",
        "File:Van Gogh - The Bedroom, 1889 Chicago.jpg",
        "bedroom.jpg",
        "traceability_core",
    ),
    CommonsAsset(
        "secret-earthrise-calibration",
        "File:Earthrise.jpg",
        "earthrise-calibration.jpg",
        "calibration",
    ),
    CommonsAsset(
        "secret-moon-calibration",
        "File:Moon.jpg",
        "moon-calibration.jpg",
        "calibration",
    ),
)


PAIR_SPECS: tuple[PairSpec, ...] = (
    PairSpec(
        "baboon-water-lilies",
        "cover-baboon",
        "secret-water-lilies",
        "traceability_core",
    ),
    PairSpec(
        "boat-great-wave",
        "cover-boat",
        "secret-great-wave",
        "traceability_core",
    ),
    PairSpec(
        "peppers-grande-jatte",
        "cover-peppers",
        "secret-grande-jatte",
        "traceability_core",
    ),
    PairSpec(
        "house-bedroom",
        "cover-house",
        "secret-bedroom",
        "traceability_core",
    ),
    PairSpec(
        "usc-4.1.07-earthrise-calibration",
        "cover-usc-4.1.07-calibration",
        "secret-earthrise-calibration",
        "calibration",
    ),
    PairSpec(
        "usc-4.1.08-moon-calibration",
        "cover-usc-4.1.08-calibration",
        "secret-moon-calibration",
        "calibration",
    ),
)


MANIFEST_FIELDS = (
    "pair_id",
    "cover",
    "secret",
    "split",
    "cover_source_id",
    "secret_source_id",
    "cover_rights",
    "secret_rights",
    "cover_sha256",
    "secret_sha256",
    "cover_array_sha256",
    "secret_array_sha256",
)
INVENTORY_FIELDS = (
    "asset_id",
    "role",
    "stratum",
    "local_path",
    "source_id",
    "source_url",
    "source_page_url",
    "rights",
    "rights_url",
    "access_date",
    "source_verification",
    "source_checksum",
    "source_bytes",
    "file_sha256",
    "decoded_array_sha256",
    "decoded_size",
    "decoded_dtype",
    "source_original_sha1",
    "source_revision_timestamp",
    "metadata_path",
    "assignment_rule",
)


def _crc_table() -> tuple[int, ...]:
    table: list[int] = []
    for value in range(256):
        crc = value << 24
        for _ in range(8):
            crc = (
                ((crc << 1) ^ 0x04C11DB7)
                if crc & 0x80000000
                else crc << 1
            ) & 0xFFFFFFFF
        table.append(crc)
    return tuple(table)


_POSIX_CRC_TABLE = _crc_table()


def posix_cksum(payload: bytes) -> tuple[int, int]:
    """Return the checksum and byte count produced by POSIX ``cksum``."""

    crc = 0
    for byte in payload:
        crc = (
            ((crc << 8) & 0xFFFFFFFF)
            ^ _POSIX_CRC_TABLE[((crc >> 24) ^ byte) & 0xFF]
        )
    length = len(payload)
    remaining = length
    while remaining:
        byte = remaining & 0xFF
        remaining >>= 8
        crc = (
            ((crc << 8) & 0xFFFFFFFF)
            ^ _POSIX_CRC_TABLE[((crc >> 24) ^ byte) & 0xFF]
        )
    return ((~crc) & 0xFFFFFFFF, length)


def _fetch_url(url: str, timeout_seconds: float) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def _retryable(error: BaseException) -> bool:
    if isinstance(error, HTTPError):
        return error.code in RETRYABLE_HTTP_STATUS
    return isinstance(
        error,
        (ConnectionError, HTTPException, OSError, TimeoutError, URLError),
    )


def fetch_with_retries(
    url: str,
    *,
    attempts: int,
    timeout_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
) -> bytes:
    if not 1 <= attempts <= 20:
        raise ValueError("attempts must be from 1 through 20")
    if timeout_seconds <= 0:
        raise ValueError("timeout must be positive")
    delay = 1.0
    for attempt in range(1, attempts + 1):
        try:
            return _fetch_url(url, timeout_seconds)
        except Exception as error:
            if attempt == attempts or not _retryable(error):
                raise
            print(
                f"download attempt {attempt}/{attempts} failed for {url}: "
                f"{type(error).__name__}: {error}; retrying in {delay:g}s",
                file=sys.stderr,
            )
            sleep(delay)
            delay = min(delay * 2.0, 30.0)
    raise AssertionError("unreachable retry state")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _valid_image_payload(payload: bytes) -> bool:
    try:
        with Image.open(BytesIO(payload)) as image:
            image.verify()
    except (OSError, SyntaxError):
        return False
    return True


def _atomic_install(path: Path, payload: bytes, *, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.part-{uuid.uuid4().hex}")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, path)
            return
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise
        finally:
            temporary.unlink(missing_ok=True)
    finally:
        temporary.unlink(missing_ok=True)


def _write_locked(
    path: Path,
    payload: bytes,
    *,
    mode: str,
    resume_validator: Callable[[bytes], bool] | None = None,
) -> str:
    if mode not in {"fail", "resume", "overwrite"}:
        raise ValueError(f"unsupported write mode: {mode}")
    if path.exists():
        if not path.is_file():
            raise LockConflict(f"locked path is not a regular file: {path}")
        if mode == "fail":
            raise FileExistsError(
                f"refusing to replace existing file: {path}; "
                "use --resume to verify/reuse or --overwrite to replace"
            )
        if mode == "resume":
            existing = path.read_bytes()
            accepted = (
                existing == payload
                if resume_validator is None
                else resume_validator(existing)
            )
            if not accepted:
                raise LockConflict(
                    f"existing locked file differs or fails validation: {path}"
                )
            return "reused"
    _atomic_install(path, payload, overwrite=mode == "overwrite")
    return "written"


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _csv_bytes(
    rows: Iterable[Mapping[str, object]],
    fields: Sequence[str],
) -> bytes:
    stream = StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=list(fields),
        extrasaction="raise",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _official_usc_checksums(page: bytes) -> dict[str, int]:
    text = page.decode("utf-8", errors="strict")
    found: dict[str, int] = {}
    for asset in USC_ASSETS:
        pattern = re.compile(
            re.escape(asset.source_path) + r"\s*<td>\s*([0-9]+)",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match is None:
            raise ValueError(
                f"USC-SIPI checksum page omits {asset.source_path}"
            )
        found[asset.source_path] = int(match.group(1))
    return found


def _commons_query_url(title: str) -> str:
    return COMMONS_API + "?" + urlencode(
        {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "imageinfo",
            "inprop": "url",
            "iiprop": (
                "url|sha1|size|mime|timestamp|canonicaltitle|extmetadata"
            ),
            "iiurlwidth": str(COMMONS_THUMB_WIDTH),
            "titles": title,
        }
    )


def _metadata_value(
    image_info: Mapping[str, Any],
    name: str,
) -> str:
    entry = image_info.get("extmetadata", {}).get(name, {})
    return unescape(str(entry.get("value", "")).strip())


def _validate_commons_page(
    asset: CommonsAsset,
    response: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    pages = response.get("query", {}).get("pages", [])
    if not isinstance(pages, list) or len(pages) != 1:
        raise ValueError(
            f"Commons API did not return exactly one page for {asset.title!r}"
        )
    page = pages[0]
    if not isinstance(page, dict) or "missing" in page:
        raise ValueError(f"Commons file is missing: {asset.title!r}")
    if page.get("title") != asset.title:
        raise ValueError(
            f"Commons title drift: expected {asset.title!r}, "
            f"received {page.get('title')!r}"
        )
    info_items = page.get("imageinfo", [])
    if not isinstance(info_items, list) or len(info_items) != 1:
        raise ValueError(
            f"Commons imageinfo is unavailable for {asset.title!r}"
        )
    info = info_items[0]
    if not isinstance(info, dict):
        raise ValueError(f"invalid Commons imageinfo for {asset.title!r}")
    required = ("url", "thumburl", "sha1", "timestamp", "mime")
    missing = [key for key in required if not info.get(key)]
    if missing:
        raise ValueError(
            f"Commons imageinfo for {asset.title!r} omits {missing}"
        )
    license_short_name = _metadata_value(info, "LicenseShortName")
    usage_terms = _metadata_value(info, "UsageTerms")
    if license_short_name not in ALLOWED_LICENSE_SHORT_NAMES:
        raise ValueError(
            f"Commons license is not in the explicit free-license allowlist "
            f"for {asset.title!r}: {license_short_name!r}"
        )
    if not usage_terms:
        raise ValueError(
            f"Commons UsageTerms is empty for {asset.title!r}"
        )
    selected = {
        "pageid": int(page["pageid"]),
        "title": str(page["title"]),
        "canonicalurl": str(
            page.get("canonicalurl")
            or (
                "https://commons.wikimedia.org/wiki/"
                + quote(str(page["title"]).replace(" ", "_"), safe=":()_-.,")
            )
        ),
        "original_url": str(info["url"]),
        "selected_download_url": str(info["thumburl"]),
        "thumbwidth": int(info.get("thumbwidth", 0)),
        "thumbheight": int(info.get("thumbheight", 0)),
        "original_sha1": str(info["sha1"]).lower(),
        "revision_timestamp": str(info["timestamp"]),
        "original_size": int(info.get("size", 0)),
        "mime": str(info["mime"]),
        "license_short_name": license_short_name,
        "usage_terms": usage_terms,
        "license_url": _metadata_value(info, "LicenseUrl"),
    }
    return dict(page), selected


def _resume_commons_metadata(
    existing: bytes,
    selected: Mapping[str, Any],
    file_sha256: str,
) -> bool:
    try:
        payload = json.loads(existing)
        locked = payload["selected"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False
    stable_fields = (
        "pageid",
        "title",
        "original_url",
        "selected_download_url",
        "original_sha1",
        "revision_timestamp",
        "license_short_name",
        "usage_terms",
    )
    return (
        all(locked.get(key) == selected.get(key) for key in stable_fields)
        and payload.get("downloaded_file_sha256") == file_sha256
    )


def _decoded_details(path: Path, *, size: int) -> dict[str, str]:
    array = load_uint8_grayscale(path, size=size)
    return {
        "decoded_array_sha256": sha256_array(array),
        "decoded_size": f"{array.shape[1]}x{array.shape[0]}",
        "decoded_dtype": str(array.dtype),
    }


def _relative(path: Path, base: Path) -> str:
    return Path(os.path.relpath(path, base)).as_posix()


def _resolve_access_date(
    lock_path: Path,
    requested: str | None,
    *,
    mode: str,
) -> str:
    if requested is not None:
        try:
            date.fromisoformat(requested)
        except ValueError as error:
            raise ValueError("--access-date must use YYYY-MM-DD") from error
    if mode == "resume" and lock_path.is_file():
        try:
            existing = json.loads(lock_path.read_text(encoding="utf-8"))
            locked_date = str(existing["access_date"])
            date.fromisoformat(locked_date)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise LockConflict(
                f"invalid existing lock metadata: {lock_path}"
            ) from error
        if requested is not None and requested != locked_date:
            raise LockConflict(
                f"requested access date {requested} differs from locked "
                f"access date {locked_date}"
            )
        return locked_date
    return requested or date.today().isoformat()


def prepare_locked_inputs(
    output_dir: Path,
    manifest_dir: Path,
    *,
    mode: str = "fail",
    attempts: int = 6,
    timeout_seconds: float = 60.0,
    access_date: str | None = None,
) -> dict[str, object]:
    """Acquire, validate, and lock six pairs and their inventories."""

    output_dir = output_dir.resolve()
    manifest_dir = manifest_dir.resolve()
    lock_path = output_dir / "lock-metadata-v2.json"
    locked_access_date = _resolve_access_date(
        lock_path,
        access_date,
        mode=mode,
    )
    lock_record = {
        "schema": LOCK_SCHEMA,
        "lock_name": LOCK_NAME,
        "access_date": locked_access_date,
        "assignment_rule": (
            "fixed-in-declared-PAIR_SPECS-order-before-results-v2"
        ),
        "commons_api": COMMONS_API,
        "commons_iiurlwidth": COMMONS_THUMB_WIDTH,
        "usc_checksum_url": USC_CHECKSUM_URL,
        "core_pair_count": 4,
        "calibration_pair_count": 2,
    }
    _write_locked(lock_path, _json_bytes(lock_record), mode=mode)

    checksum_page = fetch_with_retries(
        USC_CHECKSUM_URL,
        attempts=attempts,
        timeout_seconds=timeout_seconds,
    )
    current_checksums = _official_usc_checksums(checksum_page)
    for asset in USC_ASSETS:
        observed = current_checksums[asset.source_path]
        if observed != asset.official_posix_cksum:
            raise ValueError(
                f"USC-SIPI official checksum drift for {asset.source_path}: "
                f"locked {asset.official_posix_cksum}, current {observed}"
            )

    checksum_snapshot = {
        "schema": 1,
        "source_url": USC_CHECKSUM_URL,
        "access_date": locked_access_date,
        "source_page_sha256": _sha256_bytes(checksum_page),
        "algorithm": "POSIX cksum CRC as documented by USC-SIPI",
        "checksums": current_checksums,
    }
    checksum_snapshot_path = output_dir / "metadata" / "usc-sipi-checksums.json"
    _write_locked(
        checksum_snapshot_path,
        _json_bytes(checksum_snapshot),
        mode=mode,
        resume_validator=lambda existing: (
            json.loads(existing).get("checksums") == current_checksums
        ),
    )

    inventory: list[dict[str, object]] = []
    asset_records: dict[str, dict[str, str]] = {}

    for asset in USC_ASSETS:
        payload = fetch_with_retries(
            asset.download_url,
            attempts=attempts,
            timeout_seconds=timeout_seconds,
        )
        if not _valid_image_payload(payload):
            raise ValueError(
                f"USC-SIPI payload is not a valid image: {asset.source_path}"
            )
        observed_cksum, byte_count = posix_cksum(payload)
        if observed_cksum != asset.official_posix_cksum:
            raise ValueError(
                f"USC-SIPI POSIX cksum mismatch for {asset.source_path}: "
                f"expected {asset.official_posix_cksum}, "
                f"received {observed_cksum}"
            )
        local_path = (
            output_dir / "covers" / asset.filename
            if asset.stratum == "traceability_core"
            else output_dir / "calibration" / "covers" / asset.filename
        )
        _write_locked(local_path, payload, mode=mode)
        file_hash = sha256_file(local_path)
        decoded = _decoded_details(local_path, size=512)
        source_id = f"USC-SIPI:{asset.source_path}"
        record = {
            "asset_id": asset.asset_id,
            "role": "cover",
            "stratum": asset.stratum,
            "local_path": _relative(local_path, manifest_dir),
            "source_id": source_id,
            "source_url": asset.download_url,
            "source_page_url": USC_CATALOGUE_URL,
            "rights": asset.rights,
            "rights_url": USC_RIGHTS_URL,
            "access_date": locked_access_date,
            "source_verification": (
                f"USC-SIPI official POSIX cksum={observed_cksum}"
            ),
            "source_checksum": str(observed_cksum),
            "source_bytes": str(byte_count),
            "file_sha256": file_hash,
            **decoded,
            "source_original_sha1": "",
            "source_revision_timestamp": "",
            "metadata_path": _relative(
                checksum_snapshot_path,
                manifest_dir,
            ),
            "assignment_rule": (
                "fixed-in-declared-PAIR_SPECS-order-before-results-v2"
            ),
        }
        inventory.append(record)
        asset_records[asset.asset_id] = {
            "path": record["local_path"],
            "source_id": source_id,
            "rights": asset.rights,
            "file_sha256": file_hash,
            "decoded_array_sha256": decoded["decoded_array_sha256"],
        }
        print(f"locked USC-SIPI {asset.source_path}: {local_path}")

    for asset in COMMONS_ASSETS:
        query_url = _commons_query_url(asset.title)
        api_payload = fetch_with_retries(
            query_url,
            attempts=attempts,
            timeout_seconds=timeout_seconds,
        )
        try:
            api_response = json.loads(api_payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(
                f"invalid Commons API JSON for {asset.title!r}"
            ) from error
        page, selected = _validate_commons_page(asset, api_response)
        image_payload = fetch_with_retries(
            selected["selected_download_url"],
            attempts=attempts,
            timeout_seconds=timeout_seconds,
        )
        if not _valid_image_payload(image_payload):
            raise ValueError(
                f"Commons thumburl is not a valid image: {asset.title!r}"
            )
        local_path = (
            output_dir / "secrets" / asset.filename
            if asset.stratum == "traceability_core"
            else output_dir / "calibration" / "secrets" / asset.filename
        )
        _write_locked(local_path, image_payload, mode=mode)
        file_hash = sha256_file(local_path)
        decoded = _decoded_details(local_path, size=128)
        metadata_path = (
            output_dir / "metadata" / "commons" / f"{asset.asset_id}.json"
        )
        metadata_record = {
            "schema": 1,
            "api_endpoint": COMMONS_API,
            "api_query_url": query_url,
            "access_date": locked_access_date,
            "page": page,
            "selected": selected,
            "downloaded_file_sha256": file_hash,
            "downloaded_file_bytes": len(image_payload),
            "decoded_128x128_array_sha256": (
                decoded["decoded_array_sha256"]
            ),
        }
        _write_locked(
            metadata_path,
            _json_bytes(metadata_record),
            mode=mode,
            resume_validator=lambda existing, s=selected, h=file_hash: (
                _resume_commons_metadata(existing, s, h)
            ),
        )
        rights = (
            f"{selected['license_short_name']}; "
            f"Wikimedia UsageTerms={selected['usage_terms']}; "
            f"revision={selected['revision_timestamp']}"
        )
        rights_url = (
            str(selected["license_url"])
            or f"{selected['canonicalurl']}#Licensing"
        )
        source_id = (
            f"Wikimedia-Commons:{selected['pageid']}:"
            f"{selected['title']}"
        )
        record = {
            "asset_id": asset.asset_id,
            "role": "secret",
            "stratum": asset.stratum,
            "local_path": _relative(local_path, manifest_dir),
            "source_id": source_id,
            "source_url": selected["selected_download_url"],
            "source_page_url": selected["canonicalurl"],
            "rights": rights,
            "rights_url": rights_url,
            "access_date": locked_access_date,
            "source_verification": (
                "MediaWiki action=query imageinfo; "
                f"iiurlwidth={COMMONS_THUMB_WIDTH}; direct thumburl"
            ),
            "source_checksum": selected["original_sha1"],
            "source_bytes": str(len(image_payload)),
            "file_sha256": file_hash,
            **decoded,
            "source_original_sha1": selected["original_sha1"],
            "source_revision_timestamp": selected["revision_timestamp"],
            "metadata_path": _relative(metadata_path, manifest_dir),
            "assignment_rule": (
                "fixed-in-declared-PAIR_SPECS-order-before-results-v2"
            ),
        }
        inventory.append(record)
        asset_records[asset.asset_id] = {
            "path": record["local_path"],
            "source_id": source_id,
            "rights": rights,
            "file_sha256": file_hash,
            "decoded_array_sha256": decoded["decoded_array_sha256"],
        }
        print(f"locked Commons {asset.title}: {local_path}")

    rows_by_split: dict[str, list[dict[str, str]]] = {
        "traceability_core": [],
        "calibration": [],
    }
    for pair in PAIR_SPECS:
        cover = asset_records[pair.cover_asset_id]
        secret = asset_records[pair.secret_asset_id]
        rows_by_split[pair.split].append(
            {
                "pair_id": pair.pair_id,
                "cover": cover["path"],
                "secret": secret["path"],
                "split": pair.split,
                "cover_source_id": cover["source_id"],
                "secret_source_id": secret["source_id"],
                "cover_rights": cover["rights"],
                "secret_rights": secret["rights"],
                "cover_sha256": cover["file_sha256"],
                "secret_sha256": secret["file_sha256"],
                "cover_array_sha256": cover["decoded_array_sha256"],
                "secret_array_sha256": secret["decoded_array_sha256"],
            }
        )

    if len(rows_by_split["traceability_core"]) != 4:
        raise AssertionError("core manifest must contain exactly four rows")
    if len(rows_by_split["calibration"]) != 2:
        raise AssertionError("calibration manifest must contain exactly two rows")
    core_ids = {
        row["pair_id"] for row in rows_by_split["traceability_core"]
    }
    calibration_ids = {
        row["pair_id"] for row in rows_by_split["calibration"]
    }
    if len(core_ids) != 4 or len(calibration_ids) != 2:
        raise AssertionError("pair IDs must be unique")
    if core_ids & calibration_ids:
        raise AssertionError("core and calibration pair IDs overlap")

    core_manifest = manifest_dir / "traceability-core-v2.csv"
    calibration_manifest = manifest_dir / "calibration-v2.csv"
    inventory_manifest = manifest_dir / "source-inventory-v2.csv"
    _write_locked(
        core_manifest,
        _csv_bytes(rows_by_split["traceability_core"], MANIFEST_FIELDS),
        mode=mode,
    )
    _write_locked(
        calibration_manifest,
        _csv_bytes(rows_by_split["calibration"], MANIFEST_FIELDS),
        mode=mode,
    )
    _write_locked(
        inventory_manifest,
        _csv_bytes(inventory, INVENTORY_FIELDS),
        mode=mode,
    )
    report = {
        "status": "locked",
        "schema": LOCK_SCHEMA,
        "access_date": locked_access_date,
        "core_pair_count": 4,
        "calibration_pair_count": 2,
        "source_count": len(inventory),
        "core_manifest": str(core_manifest),
        "core_manifest_sha256": sha256_file(core_manifest),
        "calibration_manifest": str(calibration_manifest),
        "calibration_manifest_sha256": sha256_file(calibration_manifest),
        "source_inventory": str(inventory_manifest),
        "source_inventory_sha256": sha256_file(inventory_manifest),
    }
    report_path = output_dir / "locked-inputs-report-v2.json"
    _write_locked(report_path, _json_bytes(report), mode=mode)
    print(json.dumps(report, indent=2, sort_keys=True))
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download and freeze four USC-SIPI core pairs plus two "
            "calibration pairs with rights metadata and repository-contract "
            "file/decoded-array hashes."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/locked-inputs-v2"),
    )
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=Path("data-manifests"),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--resume",
        "--skip-existing",
        dest="resume",
        action="store_true",
        help=(
            "reuse only verified locked files; never replace them "
            "(--skip-existing is an alias)"
        ),
    )
    mode.add_argument(
        "--overwrite",
        action="store_true",
        help="explicitly permit replacing an existing lock",
    )
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument(
        "--access-date",
        help="locked acquisition date in YYYY-MM-DD (default: today)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    mode = (
        "resume"
        if args.resume
        else "overwrite"
        if args.overwrite
        else "fail"
    )
    prepare_locked_inputs(
        args.output_dir,
        args.manifest_dir,
        mode=mode,
        attempts=args.attempts,
        timeout_seconds=args.timeout_seconds,
        access_date=args.access_date,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
