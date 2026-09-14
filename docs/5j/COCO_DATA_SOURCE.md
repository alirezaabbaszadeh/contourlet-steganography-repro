# FINAL-5J-v1 COCO data source

## Current status

The FINAL-5J-v1 dataset is **materialized and frozen in GitHub**.

Canonical dataset materialization commit:

`2cb8bf926f6214d2e278296b32b00e9e2d3fe9f2`

Successful GitHub Actions materialization run:

`31270517507` — `Materialize frozen 5J COCO dataset`

The scientific server must consume the exact Git-tracked derived PNGs and frozen manifests. It must not reselect images or independently regenerate a different study dataset.

## Purpose

The study requires 54 candidate pairs before deterministic split freeze:

- 2 calibration pairs;
- 2 engineering dry-run pairs;
- 50 main-study pairs.

The 10 sweep pairs are selected from the frozen 50-pair main set and therefore do not require additional source pairs.

To prevent cover/secret source reuse, 54 pairs require 108 unique source images.

## Frozen source policy

Source dataset: **COCO 2017 validation**.

Official dataset site: <https://cocodataset.org/>

Official annotation object is the COCO 2017 train/validation annotation archive. The reproducibility bootstrap uses the same official COCO S3 object through an Amazon S3 TLS-valid hostname because the custom `images.cocodataset.org` hostname produced a certificate hostname mismatch on the hosted GitHub runner. TLS verification is never disabled.

Only image records whose COCO metadata declares the Creative Commons Attribution 2.0 license are eligible:

- name: `Attribution License`;
- URL: `http://creativecommons.org/licenses/by/2.0/` or HTTPS equivalent;
- local rights classification: `redistribution_permitted`.

Images under NC, ND, or other license records are excluded from this 5J source pool. The original image license remains authoritative; the COCO annotation license is not substituted for the image license.

## Outcome-blind selection

`prepare_coco_candidates.py`:

1. reads `instances_val2017.json`;
2. resolves the license record for every image;
3. keeps only CC BY 2.0 images with a minimum source dimension of 256 pixels;
4. assigns a SHA-256 selection score from protocol/version/image ID/filename;
5. takes the first 108 eligible source images in that fixed order;
6. uses positions 0--53 as cover sources and 54--107 as secret sources;
7. creates 54 unique candidate pairs.

No steganography result, image quality result, attack result, or method output is used by selection.

## Deterministic preprocessing

For each selected source image:

- decode with Pillow;
- convert to mode `L` using Pillow grayscale conversion;
- center-fit to a square;
- resize with Pillow bicubic resampling;
- write deterministic PNG with compression level 9 and optimization disabled.

Cover outputs are exactly 512x512. Secret outputs are exactly 128x128.

Preprocessing identity:

`coco2017-val-centerfit-bicubic-pillowL-v1`

The frozen provenance records source and derived SHA-256 values, original COCO dimensions, COCO image ID, COCO URL, Flickr URL, image license name/URL, and capture date when present.

## Canonical GitHub snapshot

The exact experiment bytes are stored in ordinary Git at:

- `data/5j/coco2017/prepared/covers/` — 54 grayscale 512x512 PNGs;
- `data/5j/coco2017/prepared/secrets/` — 54 grayscale 128x128 PNGs.

Associated provenance files:

- `data/5j/coco2017/prepared/candidate_pairs.csv`;
- `data/5j/coco2017/prepared/SOURCE_METADATA.json`;
- `data/5j/coco2017/prepared/ATTRIBUTION.md`;
- `data/5j/coco2017/prepared/SNAPSHOT.json`.

The snapshot inventory contains 115 dataset/provenance files totaling 8,913,690 bytes. Git LFS is not required.

Raw full-resolution COCO downloads and the annotation archive are not committed. They are temporary reproducibility inputs only.

## Frozen study manifests

The successful materialization produced:

- `data-manifests/5j/calibration.csv` — 2 pairs;
- `data-manifests/5j/dry_run.csv` — 2 pairs;
- `data-manifests/5j/main_50_pairs.csv` — exactly 50 pairs;
- `data-manifests/5j/sweep_10_pairs.csv` — exactly 10 pairs, all a subset of main;
- `data-manifests/5j/data_freeze_report.json`.

`configs/5j/data_registry_v1.json` is now `status=frozen`, `main_run_authorized=true`, with an empty blocker list.

## Reproduction/bootstrap command

The bootstrap remains available for independent reproduction of the dataset selection and preprocessing:

```bash
python scripts/5j/bootstrap_coco_data.py
```

For the actual scientific run this command is **not** the normal data source. The run must use the exact Git-tracked frozen bytes. The bootstrap is for reproducibility/audit only.

The one-shot GitHub materialization workflow is:

`.github/workflows/5j-materialize-coco-dataset.yml`

Its successful run performed download, preprocessing, split freeze, exact hash validation, dataset-size validation, raw-download cleanup, and Git commit.

## Attribution and publication

For every source image, the repository retains its COCO image ID, original source URL(s), CC BY 2.0 license URL, original dimensions, source SHA-256, derived SHA-256, and a statement that the 5J grayscale square image is a resized/converted derivative.

Source image copyright remains with the original Flickr contributor/licensor. The project does not claim that COCO owns the underlying image copyright.

`ATTRIBUTION.md` and `SOURCE_METADATA.json` must accompany the reproducibility package and final archive. If a source URL or license record later becomes unavailable, the frozen metadata and hashes remain the study identity, but publication/republication must still follow the recorded CC BY 2.0 obligations.

## Change control

The following now define the frozen scientific dataset identity:

- the 108 Git-tracked derived PNG byte streams;
- their SHA-256 values;
- the four frozen manifests;
- the pairing/split identities;
- the preprocessing identity;
- the recorded license/provenance metadata.

Changing, replacing, reprocessing, or selectively excluding any frozen study image after observing scientific outcomes requires a documented protocol revision and a new run identity.
