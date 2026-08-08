# FINAL-5J-v1 Implementation Index

This directory is the operational entry point for continuing 5J without chat history.

## Read first

1. [`AUTHOR_DECISION_FINAL_BACKUP_ONLY.md`](AUTHOR_DECISION_FINAL_BACKUP_ONLY.md) — authoritative correction: remote backup occurs once after the entire run, analysis, and manuscript package are complete.
2. [`IMPLEMENTATION_CHECKPOINT_DATASET_FROZEN_20260808.md`](IMPLEMENTATION_CHECKPOINT_DATASET_FROZEN_20260808.md) — current checkpoint: real COCO dataset materialized in GitHub, manifests frozen, and remaining execution blockers.
3. [`IMPLEMENTATION_CHECKPOINT_BASELINES_RUNNER_ANALYSIS_20260806.md`](IMPLEMENTATION_CHECKPOINT_BASELINES_RUNNER_ANALYSIS_20260806.md) — previous implementation checkpoint covering B1/B2, runner, analysis, and final archive tooling.
4. [`../FINAL_5J_IMPLEMENTATION_PLAN.md`](../FINAL_5J_IMPLEMENTATION_PLAN.md) — original comprehensive programme; backup statements conflicting with the author correction are superseded.
5. [`PROTOCOL.md`](PROTOCOL.md) — scientific scope and exact 530/8,420 design.
6. [`STATISTICAL_ANALYSIS_PLAN.md`](STATISTICAL_ANALYSIS_PLAN.md) — endpoints, comparisons, aggregation, multiplicity, and missingness.
7. [`FAILURE_SEVERITY_SPEC.md`](FAILURE_SEVERITY_SPEC.md) — S0–S6 stages, ECC overload, recovery fractions, and comparative failure reporting.
8. [`SECURITY_BACKUP_POLICY.md`](SECURITY_BACKUP_POLICY.md) — local execution reliability, secret prohibition, and one final verified archive.
9. [`DATA_AND_BASELINE_CONTRACT.md`](DATA_AND_BASELINE_CONTRACT.md) — pair provenance, rights, manifest freeze, and B1/B2 harmonization.
10. [`COCO_DATA_SOURCE.md`](COCO_DATA_SOURCE.md) — frozen COCO 2017 CC BY 2.0 source, materialization, attribution, and Git snapshot policy.

## Machine-readable authority

### Study design

- Plan: [`../../configs/5j/study_plan_v1.json`](../../configs/5j/study_plan_v1.json)
- Schema: [`../../schemas/5j/study_plan.schema.json`](../../schemas/5j/study_plan.schema.json)
- Validator: [`../../scripts/5j/validate_protocol.py`](../../scripts/5j/validate_protocol.py)
- Planner: [`../../scripts/5j/plan_run.py`](../../scripts/5j/plan_run.py)

### Frozen data

Canonical experiment bytes are now stored directly in GitHub:

- 54 covers: [`../../data/5j/coco2017/prepared/covers/`](../../data/5j/coco2017/prepared/covers/)
- 54 secrets: [`../../data/5j/coco2017/prepared/secrets/`](../../data/5j/coco2017/prepared/secrets/)
- source metadata: [`../../data/5j/coco2017/prepared/SOURCE_METADATA.json`](../../data/5j/coco2017/prepared/SOURCE_METADATA.json)
- attribution: [`../../data/5j/coco2017/prepared/ATTRIBUTION.md`](../../data/5j/coco2017/prepared/ATTRIBUTION.md)
- dataset inventory: [`../../data/5j/coco2017/prepared/SNAPSHOT.json`](../../data/5j/coco2017/prepared/SNAPSHOT.json)
- candidate pairs: [`../../data/5j/coco2017/prepared/candidate_pairs.csv`](../../data/5j/coco2017/prepared/candidate_pairs.csv)

Frozen split manifests:

- [`../../data-manifests/5j/calibration.csv`](../../data-manifests/5j/calibration.csv) — 2 pairs
- [`../../data-manifests/5j/dry_run.csv`](../../data-manifests/5j/dry_run.csv) — 2 pairs
- [`../../data-manifests/5j/main_50_pairs.csv`](../../data-manifests/5j/main_50_pairs.csv) — 50 pairs
- [`../../data-manifests/5j/sweep_10_pairs.csv`](../../data-manifests/5j/sweep_10_pairs.csv) — 10-pair subset of main
- [`../../data-manifests/5j/data_freeze_report.json`](../../data-manifests/5j/data_freeze_report.json)

Dataset materialization commit:

`2cb8bf926f6214d2e278296b32b00e9e2d3fe9f2`

The snapshot contains 108 derived PNGs and associated provenance metadata. The tracked dataset/provenance snapshot is approximately 8.9 MB, so ordinary Git is used rather than Git LFS.

### Inputs and baselines

- COCO bootstrap/reproduction tool: [`../../scripts/5j/bootstrap_coco_data.py`](../../scripts/5j/bootstrap_coco_data.py)
- COCO candidate preparer: [`../../scripts/5j/prepare_coco_candidates.py`](../../scripts/5j/prepare_coco_candidates.py)
- Deterministic split freezer: [`../../scripts/5j/freeze_data_manifests.py`](../../scripts/5j/freeze_data_manifests.py)
- Data registry: [`../../configs/5j/data_registry_v1.json`](../../configs/5j/data_registry_v1.json) — currently `frozen`, `main_run_authorized=true`
- Baseline registry: [`../../configs/5j/baseline_registry_v1.json`](../../configs/5j/baseline_registry_v1.json)
- Attack seed lock: [`../../configs/5j/seeds.lock.json`](../../configs/5j/seeds.lock.json)
- Pair schema: [`../../schemas/5j/pair_manifest.schema.json`](../../schemas/5j/pair_manifest.schema.json)
- Baseline schema: [`../../schemas/5j/baseline_contract.schema.json`](../../schemas/5j/baseline_contract.schema.json)
- Input validator: [`../../scripts/5j/validate_inputs.py`](../../scripts/5j/validate_inputs.py)
- Tracking issue: GitHub Issue #6

## Current implementation state

Implemented and frozen/scaffolded:

- protocol and exact counts;
- format-v2 Base/Detail integrity;
- C3_NP ablation;
- progressive payload support;
- failure-severity diagnostics;
- B1/B2 canonical baselines, contracts, and code freeze;
- unified seven-method local worker;
- simple two-stage local-cache dispatcher and resume;
- 16-worker engineering benchmark harness;
- deterministic COCO 2017 CC BY 2.0 acquisition/preprocessing path;
- real 108-image / 54-pair GitHub dataset materialization;
- frozen calibration/dry-run/main/sweep manifests with SHA-256 and rights metadata;
- calibration-only stability builder;
- pair-level statistical analysis, tables, and figures;
- deterministic final-only archive and verifier.

Completed data state:

- 54 real cover/secret pairs are present in GitHub;
- 108 source identities are unique across roles;
- all admitted source records carry CC BY 2.0 metadata;
- exact source and derived SHA-256 values are retained;
- `configs/5j/data_registry_v1.json` has no data blockers and authorizes the main data set;
- GitHub Actions materialization run `31270517507` completed successfully.

Remaining execution work:

- build the real target-environment PDFB stability profile from the two frozen calibration pairs;
- resolve remaining CI failures/action-required runs and obtain observable green checks for relevant workflows;
- finalize the execution plan after final source/runtime/stability freeze;
- connect the upgraded 32-CPU/64-GiB server;
- run the 16-worker benchmark and choose the fastest stable worker count;
- complete the two-pair, seven-method engineering dry run;
- execute the main study and sweeps;
- generate analysis and manuscript outputs from real results;
- perform one final verified remote backup.

No FINAL-5J-v1 scientific run has occurred yet: 0/530 embeddings and 0/8,420 evaluations.

## Execution semantics

During execution:

```text
planned
→ running
→ locally_complete
```

A locally valid cache object counts toward progress. Remote backup does not block embeddings, evaluations, resume, or progress reporting.

After all tasks and final outputs are complete:

```text
run_complete_local
→ final backup package
→ remote verification
→ project_archived
```

## Immediate execution order

The dataset is already frozen in GitHub. Do not reselect or rebuild it on the scientific server.

1. checkout the final/frozen source revision and verify data-manifest hashes;
2. build the real PDFB stability profile from `calibration.csv`;
3. finalize runtime binding and execution plan;
4. run the 16-worker benchmark on the upgraded server and adjust only from measured resource/throughput evidence;
5. run the two-pair seven-method engineering dry run;
6. execute the full 530-embedding / 8,420-evaluation study;
7. build analysis, tables, figures, and manuscript from frozen results;
8. create, upload, and verify one final backup archive.
