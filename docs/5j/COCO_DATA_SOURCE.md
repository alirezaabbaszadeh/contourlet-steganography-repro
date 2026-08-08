# FINAL-5J-v1 COCO data source

## Purpose

The study requires 54 candidate pairs before deterministic split freeze:

- 2 calibration pairs;
- 2 engineering dry-run pairs;
- 50 main-study pairs.

The 10 sweep pairs are selected from the frozen 50-pair main set and therefore
do not require additional source pairs.

To prevent cover/secret source reuse, 54 pairs require 108 unique source images.

## Frozen source policy

Source dataset: **COCO 2017 validation**.

Official dataset site: <https://cocodataset.org/>

Official annotation archive:
<https://images.cocodataset.org/annotations/annotations_trainval2017.zip>

Only image records whose COCO metadata declares the Creative Commons
Attribution 2.0 license are eligible:

- name: `Attribution License`;
- URL: `http://creativecommons.org/licenses/by/2.0/` or HTTPS equivalent;
- local rights classification: `redistribution_permitted`.

Images under NC, ND, or other license records are excluded from this 5J source
pool. The original image license remains authoritative; the COCO annotation
license is not substituted for the image license.

## Outcome-blind selection

`prepare_coco_candidates.py`:

1. reads `instances_val2017.json`;
2. resolves the license record for every image;
3. keeps only CC BY 2.0 images with a minimum source dimension of 256 pixels;
4. assigns a SHA-256 selection score from protocol/version/image ID/filename;
5. takes the first 108 eligible source images in that fixed order;
6. uses positions 0--53 as cover sources and 54--107 as secret sources;
7. creates 54 unique candidate pairs.

No steganography result, image quality result, attack result, or method output is
used by selection.

## Deterministic preprocessing

For each selected source image:

- decode with Pillow;
- convert to mode `L` using Pillow's grayscale conversion;
- center-fit to a square;
- resize with Pillow bicubic resampling;
- write deterministic PNG with compression level 9 and optimization disabled.

Cover outputs are exactly 512x512. Secret outputs are exactly 128x128.

Preprocessing identity:

`coco2017-val-centerfit-bicubic-pillowL-v1`

The preparation report records source and derived SHA-256 values, original
COCO dimensions, COCO image ID, COCO URL, Flickr URL, image license name/URL,
and capture date when present.

## One-command server bootstrap

From the repository root:

```bash
python scripts/5j/bootstrap_coco_data.py
```

The command downloads the official annotation archive, extracts only
`instances_val2017.json`, downloads the 108 selected validation images from the
COCO image host, prepares the 54 pairs, and invokes
`freeze_data_manifests.py`.

Expected frozen manifests:

- `data-manifests/5j/calibration.csv` -- 2 pairs;
- `data-manifests/5j/dry_run.csv` -- 2 pairs;
- `data-manifests/5j/main_50_pairs.csv` -- 50 pairs;
- `data-manifests/5j/sweep_10_pairs.csv` -- 10-pair subset of main;
- `data-manifests/5j/data_freeze_report.json`.

## Attribution and publication

The final data/provenance package must retain, for every source image, its COCO
image ID, original source URL(s), CC BY 2.0 license URL, and a statement that
the 5J grayscale square image is a resized/converted derivative. Source image
copyright remains with the original Flickr contributor/licensor.

The repository should not claim that COCO itself owns the underlying image
copyright. If a source URL or license record is later unavailable, the frozen
metadata and hashes remain the study identity, but publication/republication
must still follow the recorded CC BY 2.0 obligations.
