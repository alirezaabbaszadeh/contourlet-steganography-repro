# FINAL-5J-v1 Implementation Index

This directory is the operational entry point for continuing 5J without chat history.

## Authoritative decisions

- Remote backup occurs once after computation, analysis, tables, figures, manuscript, and supplement are locally complete.
- Numerical progress is based on locally hash-valid content-addressed cache objects.
- No embedding or evaluation waits for remote upload.
- No plaintext private key, PEM, token, password, license credential, or recovery key may enter Git or an archive.

## Frozen design

- 50 main cover-secret pairs;
- seven methods: `C0`, `C1`, `C2`, `C3_NP`, `C3`, `B1`, `B2`;
- 22 main channel instances;
- 530 embeddings and 8,420 evaluations;
- payload and PSNR sweeps;
- independent Base/Detail integrity for internal methods;
- pair-level statistical inference and explicit failure-severity reporting.

## Implemented core

- format-v2 Base/Detail integrity and Base-only recovery;
- isolated `C3_NP` ablation;
- progressive 25/50/75/100% payloads and dynamic RS profiles;
- S0–S6 and codeword-level ECC-overload diagnostics;
- local atomic/cache/resume runtime;
- 16-worker benchmark harness;
- unified seven-method task command and two-stage dispatcher;
- deterministic data manifest freezer;
- calibration-only stability-profile builder;
- pair-level analysis with bootstrap, Wilcoxon, and Holm correction;
- machine-generated CSV/JSONL/Parquet, tables, and figures;
- one deterministic final-only archive and independent verifier.

## Frozen baselines

### B1

Canonical grayscale k-LSB replacement, with clean-valid `k` selected from 1–4 by closest realized PSNR. External lineage is pinned to `ragibson/Steganography` commit `06a3c920420e62f2e8a0589cfd5bfb2e51be4ee8` under MIT.

### B2

Blind 8×8 orthonormal block-DCT scalar-QIM using 32 frozen AC positions per block, exact 131,072-bit capacity, frozen deltas, and bounded parity-preserving clean repair. External lineage is pinned to `MasonEdgar/DCT-Image-Steganography` commit `20da3e1e4d6b48dbcbe241c776ee156995bb65fe` under MIT.

Authority:

- `docs/5j/baselines/B1_CONTRACT.json`
- `docs/5j/baselines/B2_CONTRACT.json`
- `docs/5j/baselines/BASELINE_CLEAN_FIXTURE_EVIDENCE.json`
- `docs/5j/baselines/BASELINE_CODE_FREEZE.json`
- `scripts/5j/validate_baseline_freeze.py`

Both are canonical engineering controls, not claims of exact author-equivalent paper reproduction. Base/Detail and ECC fields are `not_applicable` for these baselines.

## Data freeze

Provide at least 54 actual, already-preprocessed, rights-documented pairs using `data-manifests/5j/candidate_pairs.template.csv`, then run:

```bash
python scripts/5j/freeze_data_manifests.py \
  --catalog /data/final-5j-candidate-pairs.csv \
  --output-dir data-manifests/5j \
  --report data-manifests/5j/data_freeze_report.json
```

Selection is outcome-blind and SHA-256 deterministic: first two calibration, next two dry-run, next 50 main, and 10 independently ranked main pairs for sweeps. The command validates rights metadata, hashes, dimensions, grayscale mode, uniqueness, and disjointness. It never invents data or rights.

## Stability profile

```bash
python scripts/5j/build_stability_profile.py \
  --manifest data-manifests/5j/calibration.csv \
  --config configs/5j/format_v2_layer_integrity.toml \
  --output /srv/ctsteg/final-5j/stability-profile.json
```

## Execution

```bash
python scripts/5j/dispatch_research.py \
  --plan /srv/ctsteg/final-5j/execution-plan-bound.json \
  --runtime-bindings /srv/ctsteg/final-5j/runtime-bindings.json \
  --science-ready-report /srv/ctsteg/final-5j/input-readiness.json \
  --repository-root /opt/ctsteg/current \
  --cache-dir /srv/ctsteg/final-5j/cache \
  --run-dir /srv/ctsteg/final-5j/run \
  --workers 16
```

Order:

```text
all embeddings
→ local validation and clean acceptance
→ all evaluations
→ run_complete_local
```

## Analysis and reporting

```bash
python scripts/5j/build_analysis.py \
  --plan /srv/ctsteg/final-5j/execution-plan-bound.json \
  --cache-dir /srv/ctsteg/final-5j/cache \
  --output-dir /srv/ctsteg/final-5j/analysis

python scripts/5j/build_tables.py \
  --analysis /srv/ctsteg/final-5j/analysis/analysis.json \
  --output-dir /srv/ctsteg/final-5j/tables

python scripts/5j/build_figures.py \
  --analysis /srv/ctsteg/final-5j/analysis/analysis.json \
  --output-dir /srv/ctsteg/final-5j/figures
```

## Final-only archive

After all computation and reporting are complete:

```bash
SOURCE_DATE_EPOCH=<frozen-release-epoch> \
python scripts/5j/build_final_archive.py \
  --include cache=/srv/ctsteg/final-5j/cache \
  --include run=/srv/ctsteg/final-5j/run \
  --include analysis=/srv/ctsteg/final-5j/analysis \
  --include tables=/srv/ctsteg/final-5j/tables \
  --include figures=/srv/ctsteg/final-5j/figures \
  --include manuscript=/srv/ctsteg/final-5j/manuscript-package \
  --output /srv/ctsteg/FINAL-5J-v1-evidence.tar.gz \
  --run-id <RUN_ID> \
  --plan-id <PLAN_ID> \
  --classification restricted_encrypted_destination

python scripts/5j/verify_final_archive.py \
  --archive /srv/ctsteg/FINAL-5J-v1-evidence.tar.gz \
  --expected-sha256 <ARCHIVE_SHA256> \
  --output /srv/ctsteg/final-backup-verification.json
```

## Remaining external blockers

1. at least 54 real, rights-documented image pairs;
2. real PDFB stability calibration on the target environment;
3. final runtime binding and rebuilt execution plan after source freeze;
4. observable green CI or concrete CI fixes;
5. 32-CPU server access and 16-worker benchmark;
6. two-pair dry run and full numerical execution;
7. result-driven narrative manuscript revision;
8. one final upload and independent archive verification.

Detailed checkpoint: `IMPLEMENTATION_CHECKPOINT_BASELINES_RUNNER_ANALYSIS_20260806.md`. Tracking authority: GitHub Issue #6.
