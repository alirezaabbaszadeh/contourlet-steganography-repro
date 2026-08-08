# FINAL-5J-v1 checkpoint: frozen GitHub dataset and execution-ready inputs

Date: 2026-08-08  
Branch: `agent/runtime-resume-gate`  
Dataset materialization commit: `2cb8bf926f6214d2e278296b32b00e9e2d3fe9f2`

> Newer execution/CI checkpoint: `IMPLEMENTATION_CHECKPOINT_CI_PLAN_READY_20260808.md`.
> This file remains the authoritative dataset-freeze record.

## Frozen dataset

The real study dataset is no longer an external blocker. The exact experiment bytes are materialized in GitHub and are the canonical data source for FINAL-5J-v1.

GitHub Actions run `31270517507` (`Materialize frozen 5J COCO dataset`) completed successfully. TLS verification remained enabled; the successful download used the official COCO S3 bucket through a hostname with a valid certificate.

Source: COCO 2017 validation. Only source records carrying CC BY 2.0 / `Attribution License` metadata were admitted.

Deterministic source selection and preprocessing produced:

- 108 unique source-image identities;
- 54 grayscale cover PNGs at exactly 512x512;
- 54 grayscale secret PNGs at exactly 128x128;
- no source reuse across cover or secret roles;
- preprocessing identity `coco2017-val-centerfit-bicubic-pillowL-v1`;
- exact source and derived SHA-256 provenance.

The tracked dataset/provenance snapshot contains 115 files totaling 8,913,690 bytes. Ordinary Git is used; Git LFS is not required.

## Canonical paths

- `data/5j/coco2017/prepared/covers/`
- `data/5j/coco2017/prepared/secrets/`
- `data/5j/coco2017/prepared/candidate_pairs.csv`
- `data/5j/coco2017/prepared/SOURCE_METADATA.json`
- `data/5j/coco2017/prepared/ATTRIBUTION.md`
- `data/5j/coco2017/prepared/SNAPSHOT.json`

Frozen manifests:

- `data-manifests/5j/calibration.csv` -- 2 pairs;
- `data-manifests/5j/dry_run.csv` -- 2 pairs;
- `data-manifests/5j/main_50_pairs.csv` -- exactly 50 pairs;
- `data-manifests/5j/sweep_10_pairs.csv` -- exactly 10 pairs, all a subset of main;
- `data-manifests/5j/data_freeze_report.json`.

`configs/5j/data_registry_v1.json` is `frozen`, has `main_run_authorized=true`, and has no data blockers.

## Outcome-blind split

- first 2 protocol-ranked pairs: calibration;
- next 2: engineering dry run;
- next 50: main study;
- 10 independently ranked main pairs: sweep subset.

No steganography outcome influenced source selection, pairing, or split assignment.

## Rights and attribution

For every source image, `SOURCE_METADATA.json` retains COCO image ID, original source URL, Flickr URL when present, original dimensions, capture date when present, license ID/name/URL, source SHA-256, derived SHA-256, and derived repository path.

`ATTRIBUTION.md` is part of the frozen snapshot. The project does not claim that COCO owns underlying image copyright; recorded CC BY 2.0 obligations remain attached to the original licensors.

## Server rule

The numerical server must consume these exact Git-tracked bytes. It must not reselect or independently regenerate the study dataset.

Normal preparation is now:

```text
git checkout reviewed commit
→ verify frozen manifests and image SHA-256
→ build real two-cover PDFB stability profile
→ automatically freeze runtime bindings and final plan
→ benchmark and dry run
→ execute FINAL-5J-v1
```

## Status updates after dataset freeze

The following items that were previously listed as blockers in this checkpoint are now resolved:

- relevant 5J CI stale failures: **resolved**;
- production logical execution-plan expansion: **resolved and CI-validated**;
- manual runtime-binding JSON preparation: **removed; automatic freezer implemented**;
- final-plan orchestration: **implemented as one command after real stability exists**.

Production logical plan validated by workflow run `31271451804`:

```text
plan_id = 06b512c1cb6e6e8e1d5c97ec68b6450552a49fa03378d421e5cd13e5953b212a
530 embeddings
8420 evaluations
```

This is intentionally the unbound logical plan. The final scientific plan/run ID is generated only after the real target runtime and stability profile are bound.

## Remaining machine-dependent work

1. Connect/check out the reviewed commit on the upgraded 32-CPU/64-GiB server.
2. Build the real PDFB stability profile using the two frozen calibration pairs.
3. Run `prepare_final_execution_plan.py` to bind Octave/toolbox/Stage-0/stability and produce the final plan/run ID.
4. Run the initial 16-worker benchmark and select the fastest stable worker count from measured data.
5. Run the two-pair, seven-method engineering dry run.
6. Execute 350 main embeddings / 7,700 main evaluations.
7. Execute payload sweep: +90 / +360.
8. Execute PSNR sweep: +90 / +360.
9. Generate frozen analysis, tables, figures, manuscript, and supplement.
10. Build, upload, and independently verify one final project archive.

Scientific execution remains 0/530 embeddings and 0/8,420 evaluations.

## Backup rule

Remote backup does not participate in numerical scheduling. During execution, locally valid cache objects count as progress. One remote archive is created and verified only after all computation and final publication artifacts are locally complete.
