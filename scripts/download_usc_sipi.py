#!/usr/bin/env python3
"""Download the USC-SIPI images named or plausibly implied by the article."""

from __future__ import annotations

import argparse
from pathlib import Path
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


def download(name: str, identifier: str, destination: Path) -> None:
    query = urlencode({"img": identifier, "vol": "misc"})
    url = f"https://sipi.usc.edu/database/download.php?{query}"
    request = Request(url, headers={"User-Agent": "ctsteg-reproduction/0.2"})
    with urlopen(request, timeout=60) as response:
        payload = response.read()
    output = destination / f"{name}.tiff"
    output.write_bytes(payload)
    with Image.open(output) as image:
        image.verify()
    print(f"saved {name}: {output}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("data/usc_sipi"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, identifier in IMAGES.items():
        download(name, identifier, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
