# FINAL-5J-v1 checkpoint: frozen GitHub dataset and execution-ready inputs

Date: 2026-08-08  
Branch: `agent/runtime-resume-gate`  
Dataset materialization commit: `2cb8bf926f6214d2e278296b32b00e9e2d3fe9f2`

## What changed since the 2026-08-06 checkpoint

The real study dataset is no longer an external blocker. The exact experiment bytes are now materialized in GitHub and are the canonical data source for FINAL-5J-v1.

GitHub Actions run `31270517507` (`Materialize frozen 5J COCO dataset`) completed successfully after the COCO download endpoint was changed from the failing custom TLS hostname to the same official COCO S3 bucket through the valid Amazon S3 hostname. TLS verification was not disabled.

The successful job completed all of these stages:

1. checkout and Python setup;
2. project installation and command compilation;
3. COCO annotation/image download;
4. deterministic CC BY 2.0 source filtering;
5. deterministic preprocessing;
6. deterministic 54-pair split freeze;
7. sanitized source/attribution metadata generation;
8. exact file/hash validation;
9. repository size validation;
10. removal of raw full-resolution COCO downloads;
11. commit of only the exact experiment bytes and provenance metadata.

## Canonical frozen dataset

Source: COCO 2017 validation.

Eligibility:

- image metadata license must be Creative Commons Attribution 2.0 (`CC BY 2.0`);
- minimum original image dimension is 256 pixels;
- no scientific result or steganography outcome participates in image selection.

Selection and pairing:

- 108 unique source images are selected by protocol-domain SHA-256 order;
- positions 0--53 become cover sources;
- positions 54--107 become secret sources;
- no source image is reused across cover or secret roles;
- 54 unique cover/secret pairs are produced.

Deterministic preprocessing identity:

`coco2017-val-centerfit-bicubic-pillowL-v1`

Derived experiment bytes:

- 54 grayscale cover PNGs at exactly 512x512;
- 54 grayscale secret PNGs at exactly 128x128;
- 108 derived PNGs total;
- exact derived and source SHA-256 values are recorded.

The generated Git snapshot contains 115 tracked dataset/provenance files totaling 8,913,690 bytes. The derived image set is therefore intentionally stored with ordinary Git; Git LFS is not required.

## Canonical repository paths

Experiment bytes and provenance:

- `data/5j/coco2017/prepared/covers/`
- `data/5j/coco2017/prepared/secrets/`
- `data/5j/coco2017/prepared/candidate_pairs.csv`
- `data/5j/coco2017/prepared/SOURCE_METADATA.json`
- `data/5j/coco2017/prepared/ATTRIBUTION.md`
- `data/5j/coco2017/prepared/SNAPSHOT.json`

Frozen study manifests:

- `data-manifests/5j/calibration.csv` -- 2 pairs;
- `data-manifests/5j/dry_run.csv` -- 2 pairs;
- `data-manifests/5j/main_50_pairs.csv` -- exactly 50 pairs;
- `data-manifests/5j/sweep_10_pairs.csv` -- exactly 10 pairs, all a subset of main;
- `data-manifests/5j/data_freeze_report.json`.

The frozen split is outcome-blind:

- first 2 protocol-ranked pairs: calibration;
- next 2: engineering dry run;
- next 50: main study;
- 10 independently ranked main pairs: sweep subset.

## Data registry state

`configs/5j/data_registry_v1.json` is now:

- `status: frozen`;
- `main_run_authorized: true`;
- `blockers: []`;
- hashes required;
- rights metadata required;
- calibration/dry-run/main disjointness required by pair ID and image SHA-256.

This closes the previous blockers:

- provide at least 54 real preprocessed pairs;
- provide explicit rights metadata;
- freeze calibration/dry-run/main/sweep manifests;
- freeze exact image hashes.

## Rights and attribution

Only source records carrying the COCO metadata license `Attribution License` / CC BY 2.0 were admitted.

For every source image, `SOURCE_METADATA.json` retains:

- COCO image ID;
- original COCO URL;
- Flickr URL when present;
- original dimensions;
- capture date when present;
- license ID, name, and URL;
- SHA-256 of the downloaded source image;
- SHA-256 and repository path of the derived experiment PNG.

`ATTRIBUTION.md` is part of the frozen dataset snapshot. The project does not claim that COCO owns underlying image copyright; attribution and license obligations remain attached to the original licensors.

## Server behavior from this checkpoint onward

The target numerical server must consume the exact Git-tracked bytes. It must not reselect images or independently rebuild the study dataset for the scientific run.

Normal server preparation is therefore:

```text
git checkout frozen source commit
→ verify manifests and image SHA-256
→ build target PDFB stability profile from the two frozen calibration pairs
→ finalize execution plan/runtime binding
→ run benchmark and dry run
→ execute FINAL-5J-v1
```

The COCO bootstrap/materialization workflow remains reproducibility tooling, not a required step on every scientific server.

## Baselines and runtime status

The previous checkpoint remains authoritative for the implemented numerical components:

- B1 canonical grayscale k-LSB baseline;
- B2 blind block-DCT scalar-QIM baseline;
- frozen baseline contracts and code-freeze validator;
- C0/C1/C2/C3_NP/C3 internal methods;
- unified seven-method worker;
- simple local-cache multi-process dispatcher;
- 16-worker engineering benchmark harness;
- payload and PSNR sweep support;
- failure-severity and Base/Detail diagnostics;
- pair-level analysis, tables, and figures;
- one final-only archive builder and verifier.

## Backup rule remains unchanged

Remote backup does not participate in numerical scheduling.

During execution:

```text
planned
→ running
→ locally_complete
```

After all computation, analysis, tables, figures, manuscript, supplement, logs, and inventories are locally complete:

```text
run_complete_local
→ one final archive
→ upload
→ remote hash verification
→ project_archived
```

## Remaining blockers after dataset freeze

1. Build and freeze the real target-environment PDFB stability profile using the two frozen calibration pairs.
2. Resolve remaining GitHub Actions failures/action-required states and obtain observable green checks for the relevant implementation workflows.
3. Finalize the execution plan after the final source/runtime/stability freeze.
4. Connect the upgraded 32-CPU/64-GiB server.
5. Run the initial 16-worker benchmark and choose the fastest stable worker count from measured throughput/resource data.
6. Run the two-pair, seven-method engineering dry run using the frozen dry-run pairs.
7. Execute the 350 main embeddings and 7,700 main evaluations.
8. Execute the payload sweep: 90 additional embeddings and 360 evaluations.
9. Execute the PSNR sweep: 90 additional embeddings and 360 evaluations.
10. Generate the frozen analysis, tables, and figures from real results.
11. Revise and compile the manuscript/supplement from frozen results.
12. Build, upload, and independently verify one final project archive.

Scientific execution has not yet occurred under FINAL-5J-v1. Current scientific count remains 0/530 embeddings and 0/8,420 evaluations.

## Immediate continuation order

```text
frozen GitHub dataset
→ target PDFB stability profile
→ final execution plan
→ 16-worker benchmark
→ two-pair seven-method dry run
→ full 5J execution
→ analysis/tables/figures
→ manuscript revision
→ one final verified archive
```
