#!/usr/bin/env python3
"""Download the USC-SIPI images named or plausibly implied by the article."""

from __future__ import annotations

import argparse
from http.client import HTTPException
from io import BytesIO
import os
from pathlib import Path
import sys
import time
from typing import Callable
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image


IMAGES = {
    "baboon": "4.2.03",
    "peppers": "4.2.07",
    "house": "house",
    "aerial": "5.1.10",
    "boat": "boat.512",
    # The article says "Jet" but the current USC-SIPI Misc catalogue has no
    # such label.  F-16 is a documented proxy and must not be treated as a
    # confirmed identification of the authors' input.
    "jet_unverified_proxy": "4.2.05",
}
RETRYABLE_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


def _valid_image(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
    except (OSError, SyntaxError):
        return False
    return True


def _retryable_network_error(error: BaseException) -> bool:
    if isinstance(error, HTTPError):
        return error.code in RETRYABLE_HTTP_STATUS
    return isinstance(
        error,
        (ConnectionError, HTTPException, OSError, TimeoutError, URLError),
    )


def _download_payload(request: Request, timeout_seconds: float) -> bytes:
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def _valid_image_payload(payload: bytes) -> bool:
    try:
        with Image.open(BytesIO(payload)) as image:
            image.verify()
    except (OSError, SyntaxError):
        return False
    return True


def download(
    name: str,
    identifier: str,
    destination: Path,
    *,
    skip_existing: bool = False,
    attempts: int = 6,
    initial_backoff_seconds: float = 2.0,
    maximum_backoff_seconds: float = 30.0,
    timeout_seconds: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    if not 1 <= attempts <= 20:
        raise ValueError("attempts must be from 1 through 20")
    if initial_backoff_seconds < 0:
        raise ValueError("initial backoff must not be negative")
    if maximum_backoff_seconds < initial_backoff_seconds:
        raise ValueError("maximum backoff must be at least the initial backoff")
    if timeout_seconds <= 0:
        raise ValueError("timeout must be positive")
    output = destination / f"{name}.tiff"
    if skip_existing and output.is_file() and _valid_image(output):
        print(f"verified existing {name}: {output}")
        return
    query = urlencode({"img": identifier, "vol": "misc"})
    url = f"https://sipi.usc.edu/database/download.php?{query}"
    request = Request(url, headers={"User-Agent": "ctsteg-reproduction/0.2"})
    delay = initial_backoff_seconds
    payload: bytes | None = None
    for attempt in range(1, attempts + 1):
        try:
            candidate = _download_payload(request, timeout_seconds)
        except Exception as error:
            if not _retryable_network_error(error) or attempt == attempts:
                raise
            print(
                f"download {name}: attempt {attempt}/{attempts} failed "
                f"({type(error).__name__}: {error}); retrying in {delay:g}s",
                file=sys.stderr,
            )
        else:
            if _valid_image_payload(candidate):
                payload = candidate
                if attempt > 1:
                    print(
                        f"download {name}: recovered on attempt "
                        f"{attempt}/{attempts}",
                        file=sys.stderr,
                    )
                break
            if attempt == attempts:
                raise ValueError(
                    f"downloaded payload is not a valid image after "
                    f"{attempts} attempts: {name}"
                )
            print(
                f"download {name}: attempt {attempt}/{attempts} returned "
                f"an invalid image; retrying in {delay:g}s",
                file=sys.stderr,
            )
        sleep(delay)
        delay = min(delay * 2, maximum_backoff_seconds)
    if payload is None:
        raise RuntimeError(f"download retry loop ended without payload: {name}")
    temporary = destination / f".{output.name}.part-{uuid.uuid4().hex}"
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if not _valid_image(temporary):
            raise ValueError(f"validated payload became unreadable: {name}")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"saved {name}: {output}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("data/usc_sipi"))
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--initial-backoff-seconds", type=float, default=2.0)
    parser.add_argument("--maximum-backoff-seconds", type=float, default=30.0)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, identifier in IMAGES.items():
        download(
            name,
            identifier,
            args.output_dir,
            skip_existing=args.skip_existing,
            attempts=args.attempts,
            initial_backoff_seconds=args.initial_backoff_seconds,
            maximum_backoff_seconds=args.maximum_backoff_seconds,
            timeout_seconds=args.timeout_seconds,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
