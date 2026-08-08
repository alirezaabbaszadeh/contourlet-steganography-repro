# FINAL-5J-v1 Implementation Index

This directory is the operational entry point for continuing 5J without chat history.

## Read first

1. [`AUTHOR_DECISION_FINAL_BACKUP_ONLY.md`](AUTHOR_DECISION_FINAL_BACKUP_ONLY.md) — authoritative correction: remote backup occurs once after the entire run, analysis, and manuscript package are complete.
2. [`IMPLEMENTATION_CHECKPOINT_CI_PLAN_READY_20260808.md`](IMPLEMENTATION_CHECKPOINT_CI_PLAN_READY_20260808.md) — current checkpoint: relevant CI repaired, production logical plan validated, and server-side stability/runtime finalization automated.
3. [`IMPLEMENTATION_CHECKPOINT_DATASET_FROZEN_20260808.md`](IMPLEMENTATION_CHECKPOINT_DATASET_FROZEN_20260808.md) — frozen real COCO dataset and manifest checkpoint.
4. [`IMPLEMENTATION_CHECKPOINT_BASELINES_RUNNER_ANALYSIS_20260806.md`](IMPLEMENTATION_CHECKPOINT_BASELINES_RUNNER_ANALYSIS_20260806.md) — historical implementation checkpoint covering B1/B2, runner, analysis, and final archive tooling.
5. [`RUNTIME_BINDING_AND_PLAN_FINALIZATION.md`](RUNTIME_BINDING_AND_PLAN_FINALIZATION.md) — current server-finalization and execution runbook.
6. [`../FINAL_5J_IMPLEMENTATION_PLAN.md`](../FINAL_5J_IMPLEMENTATION_PLAN.md) — original comprehensive programme; backup statements conflicting with the author correction are superseded.
7. [`PROTOCOL.md`](PROTOCOL.md) — scientific scope and exact 530/8,420 design.
8. [`STATISTICAL_ANALYSIS_PLAN.md`](STATISTICAL_ANALYSIS_PLAN.md) — endpoints, comparisons, aggregation, multiplicity, and missingness.
9. [`FAILURE_SEVERITY_SPEC.md`](FAILURE_SEVERITY_SPEC.md) — S0–S6 stages, ECC overload, recovery fractions, and comparative failure reporting.
10. [`COCO_DATA_SOURCE.md`](COCO_DATA_SOURCE.md) — frozen COCO 2017 CC BY 2.0 source, materialization, attribution, and Git snapshot policy.

## Machine-readable authority

### Study design

- Plan: [`../../configs/5j/study_plan_v1.json`](../../configs/5j/study_plan_v1.json)
- Schema: [`../../schemas/5j/study_plan.schema.json`](../../schemas/5j/study_plan.schema.json)
- Validator: [`../../scripts/5j/validate_protocol.py`](../../scripts/5j/validate_protocol.py)
- Logical plan builder: [`../../scripts/5j/build_execution_plan.py`](../../scripts/5j/build_execution_plan.py)
- Runtime binding freezer: [`../../scripts/5j/freeze_runtime_bindings.py`](../../scripts/5j/freeze_runtime_bindings.py)
- Final plan preparer: [`../../scripts/5j/prepare_final_execution_plan.py`](../../scripts/5j/prepare_final_execution_plan.py)

### Frozen data

Canonical experiment bytes are stored directly in GitHub:

- 54 covers: [`../../data/5j/coco2017/prepared/covers/`](../../data/5j/coco2017/prepared/covers/)
- 54 secrets: [`../../data/5j/coco2017/prepared/secrets/`](../../data/5j/coco2017/prepared/secrets/)
- source metadata: [`../../data/5j/coco2017/prepared/SOURCE_METADATA.json`](../../data/5j/coco2017/prepared/SOURCE_METADATA.json)
- attribution: [`../../data/5j/coco2017/prepared/ATTRIBUTION.md`](../../data/5j/coco2017/prepared/ATTRIBUTION.md)
- dataset inventory: [`../../data/5j/coco2017/prepared/SNAPSHOT.json`](../../data/5j/coco2017/prepared/SNAPSHOT.json)

Frozen split manifests:

- [`../../data-manifests/5j/calibration.csv`](../../data-manifests/5j/calibration.csv) — 2 pairs
- [`../../data-manifests/5j/dry_run.csv`](../../data-manifests/5j/dry_run.csv) — 2 pairs
- [`../../data-manifests/5j/main_50_pairs.csv`](../../data-manifests/5j/main_50_pairs.csv) — 50 pairs
- [`../../data-manifests/5j/sweep_10_pairs.csv`](../../data-manifests/5j/sweep_10_pairs.csv) — 10-pair subset of main

Dataset materialization commit:

`2cb8bf926f6214d2e278296b32b00e9e2d3fe9f2`

The tracked dataset/provenance snapshot is approximately 8.9 MB; ordinary Git is used rather than Git LFS.

### Inputs and baselines

- Data registry: [`../../configs/5j/data_registry_v1.json`](../../configs/5j/data_registry_v1.json) — `frozen`, `main_run_authorized=true`
- Baseline registry: [`../../configs/5j/baseline_registry_v1.json`](../../configs/5j/baseline_registry_v1.json)
- Attack seed lock: [`../../configs/5j/seeds.lock.json`](../../configs/5j/seeds.lock.json)
- Input validator: [`../../scripts/5j/validate_inputs.py`](../../scripts/5j/validate_inputs.py)
- Stability builder: [`../../scripts/5j/build_stability_profile.py`](../../scripts/5j/build_stability_profile.py)
- Tracking issue: GitHub Issue #6

## Current implementation state

Implemented and validated/scaffolded:

- protocol and exact 530/8,420 counts;
- format-v2 Base/Detail integrity;
- C3_NP ablation;
- progressive payload support;
- failure-severity diagnostics;
- B1/B2 canonical baselines, contracts, and code freeze;
- unified seven-method local worker;
- simple two-stage local-cache dispatcher and resume;
- 16-worker engineering benchmark harness;
- real 108-image / 54-pair GitHub dataset materialization;
- frozen calibration/dry-run/main/sweep manifests with SHA-256 and rights metadata;
- path-independent calibration-only stability builder;
- automatic runtime/toolbox/Stage-0/stability binding freeze;
- one-command runtime-bound final-plan preparation;
- pair-level statistical analysis, tables, and figures;
- deterministic final-only archive and verifier.

## CI state

The stale CI assumptions have been repaired. At commit
`19dcf3b40140802733b6161f475d5a0b111d8b06`, all reported 5J workflows
completed successfully. Subsequent runner-preflight run `31271680057` also
passed the new automatic runtime-freeze and path-independent stability tests.

The production logical execution-plan workflow run `31271451804` succeeded and
expanded the exact real matrix:

```text
530 embeddings
8420 evaluations
```

Logical plan identity from that run:

```text
06b512c1cb6e6e8e1d5c97ec68b6450552a49fa03378d421e5cd13e5953b212a
```

This is deliberately an unbound logical plan. The final scientific `plan_id`
and `run_id` are created only after the real server Octave/PDFB runtime,
Stage-0 evidence, and stability profile are hashed and validated.

## Remaining execution work

Repository implementation is no longer blocked by CI, data, baselines, or task expansion. The remaining machine-dependent sequence is:

1. connect/check out the reviewed commit on the upgraded 32-CPU/64-GiB server;
2. build the real PDFB stability profile from the two frozen calibration covers;
3. run `prepare_final_execution_plan.py` to freeze runtime bindings and create the final bound plan/run ID;
4. run the 16-worker benchmark and choose the fastest stable worker count;
5. complete the two-pair, seven-method engineering dry run;
6. execute the main study and sweeps;
7. generate analysis and manuscript outputs from real results;
8. perform one final verified remote backup.

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
