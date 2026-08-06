# FINAL-5J-v1 Implementation Index

This directory is the operational entry point for continuing 5J without chat history.

## Read first

1. [`AUTHOR_DECISION_FINAL_BACKUP_ONLY.md`](AUTHOR_DECISION_FINAL_BACKUP_ONLY.md) — authoritative correction: remote backup occurs once after the entire run, analysis, and manuscript package are complete.
2. [`../FINAL_5J_IMPLEMENTATION_PLAN.md`](../FINAL_5J_IMPLEMENTATION_PLAN.md) — original programme; any backup statement conflicting with the author correction is superseded.
3. [`PROTOCOL.md`](PROTOCOL.md) — scientific scope and exact 530/8,420 design.
4. [`STATISTICAL_ANALYSIS_PLAN.md`](STATISTICAL_ANALYSIS_PLAN.md) — endpoints, pair-level aggregation, multiplicity, and missingness.
5. [`FAILURE_SEVERITY_SPEC.md`](FAILURE_SEVERITY_SPEC.md) — S0–S6 stages, ECC overload, and recovery fractions.
6. [`SECURITY_BACKUP_POLICY.md`](SECURITY_BACKUP_POLICY.md) — local execution reliability, secret prohibition, and one final verified archive.
7. [`DATA_AND_BASELINE_CONTRACT.md`](DATA_AND_BASELINE_CONTRACT.md) — provenance, rights, manifest freeze, and harmonized baselines.

## Frozen scientific design

- 50 main cover-secret pairs;
- 7 methods: `C0`, `C1`, `C2`, `C3_NP`, `C3`, `B1`, `B2`;
- 22 main channel instances;
- 530 embeddings;
- 8,420 evaluations;
- payload and PSNR sweeps;
- independent Base and Detail integrity for internal layered methods;
- pair-clustered inference and explicit failure-severity reporting.

## Implemented algorithm and runtime

- format-v2 independent Base/Detail integrity;
- valid Base-only recovery;
- isolated `C3_NP` placement ablation;
- progressive 25/50/75/100% payloads;
- dynamic Reed–Solomon profiles;
- codeword-level ECC overload and S0–S6 diagnostics;
- content-addressed local cache, atomic commit, quarantine, and resume;
- unified seven-method single-task command: `scripts/5j/run_task.py`;
- simple two-stage multi-process dispatcher: `scripts/5j/dispatch_research.py`;
- default 16 workers, one thread per worker, safe CPU/RAM bounds;
- no remote backup or remote acknowledgement inside scheduling.

## Frozen baselines

### B1

`B1` is a self-contained canonical grayscale k-LSB replacement baseline:

- lineage reference: `ragibson/Steganography`;
- pinned reference commit: `06a3c920420e62f2e8a0589cfd5bfb2e51be4ee8`;
- compatible MIT license;
- candidate `k` values: 1–4;
- only clean-bit-exact candidates are accepted;
- realized PSNR closest to the requested target is selected.

Contract: [`baselines/B1_CONTRACT.json`](baselines/B1_CONTRACT.json)

### B2

`B2` is a self-contained blind block-DCT scalar-QIM baseline:

- lineage reference: `MasonEdgar/DCT-Image-Steganography`;
- pinned reference commit: `20da3e1e4d6b48dbcbe241c776ee156995bb65fe`;
- compatible MIT license;
- 8×8 orthonormal DCT;
- 32 frozen AC positions per block, exactly 131,072-bit full capacity;
- frozen QIM-delta candidates;
- bounded parity-preserving clean repair;
- only clean-bit-exact candidates are accepted;
- realized PSNR closest to the requested target is selected.

Contract: [`baselines/B2_CONTRACT.json`](baselines/B2_CONTRACT.json)

The contracts explicitly classify both methods as canonical engineering baselines rather than exact author-equivalent reproductions of peer-reviewed methods. Base/Detail and ECC fields are `not_applicable` for both baselines.

## Data preparation

Candidate catalog template:

```text
data-manifests/5j/candidate_pairs.template.csv
```

Freeze command:

```bash
python scripts/5j/freeze_data_manifests.py \
  --catalog /data/final-5j-candidate-pairs.csv \
  --output-dir data-manifests/5j \
  --report data-manifests/5j/data_freeze_report.json
```

The command validates image bytes, dimensions, grayscale mode, rights metadata, uniqueness, and disjointness. Selection is outcome-blind and hash-deterministic:

```text
first 2  -> calibration
next 2   -> engineering dry run
next 50  -> main study
10 main pairs with independent lowest sweep score -> sweep subset
```

No data or rights information is invented. At least 54 actual valid candidate pairs are required.

## Stability profile

```bash
python scripts/5j/build_stability_profile.py \
  --manifest data-manifests/5j/calibration.csv \
  --config configs/5j/format_v2_layer_integrity.toml \
  --output /srv/ctsteg/final-5j/stability-profile.json
```

The profile uses calibration covers only and records manifest, input, config, and transform fingerprints.

## Execution

After data, runtime binding, and science-readiness gates pass:

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

Execution semantics:

```text
all embeddings
→ local hash/schema and clean-round-trip acceptance
→ all evaluations
→ run_complete_local
```

A valid local object counts toward progress. Resume reads the local immutable cache. Remote backup is not consulted.

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

Outputs include:

- raw JSONL/CSV and optional Parquet;
- pair×method×condition rows;
- one overall row per pair and method;
- method summaries;
- C3–C0, C3–C3_NP, C3–B1, and C3–B2 paired effects;
- cluster bootstrap confidence intervals;
- paired Wilcoxon tests;
- Holm-adjusted p-values;
- failure-stage distributions;
- Markdown, CSV, and LaTeX tables;
- PNG and PDF figures.

## Final-only archive

Only after computation, analysis, tables, figures, manuscript, and supplement are complete:

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

The builder rejects symlinks, PEM/private-key filenames, private-key headers, and common GitHub token patterns. Restricted evidence must be uploaded only to an encrypted/private destination; the decryption key remains outside GitHub.

## Current blockers requiring external bytes or infrastructure

The remaining blockers are not missing algorithm code:

1. supply at least 54 real, rights-documented preprocessed pairs;
2. run the deterministic manifest freezer;
3. build the real PDFB stability profile on the target environment;
4. produce the finalized runtime-bound execution plan;
5. observe green CI or fix concrete workflow failures;
6. run the 16-worker engineering benchmark on the upgraded server;
7. run two-pair dry run, then the full study;
8. revise narrative manuscript text after frozen results exist;
9. create and verify the one final archive.

GitHub Issue #6 is the tracking authority.
