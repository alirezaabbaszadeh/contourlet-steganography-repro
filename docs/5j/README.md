# FINAL-5J-v1 Implementation Index

This directory is the operational entry point for continuing 5J without chat history.

## Read first

1. [`AUTHOR_DECISION_FINAL_BACKUP_ONLY.md`](AUTHOR_DECISION_FINAL_BACKUP_ONLY.md) — authoritative correction: remote backup occurs once after the entire run, analysis, and manuscript package are complete.
2. [`IMPLEMENTATION_CHECKPOINT_CI_PLAN_READY_20260808.md`](IMPLEMENTATION_CHECKPOINT_CI_PLAN_READY_20260808.md) — current checkpoint: relevant CI repaired, production logical plan validated, and server-side stability/runtime finalization automated.
3. [`IMPLEMENTATION_CHECKPOINT_DATASET_FROZEN_20260808.md`](IMPLEMENTATION_CHECKPOINT_DATASET_FROZEN_20260808.md) — frozen real COCO dataset and manifest checkpoint.
4. [`IMPLEMENTATION_CHECKPOINT_BASELINES_RUNNER_ANALYSIS_20260806.md`](IMPLEMENTATION_CHECKPOINT_BASELINES_RUNNER_ANALYSIS_20260806.md) — historical implementation checkpoint covering B1/B2, runner, analysis, and final archive tooling.
5. [`RUNTIME_BINDING_AND_PLAN_FINALIZATION.md`](RUNTIME_BINDING_AND_PLAN_FINALIZATION.md) — current server-finalization and execution runbook.
6. [`PROTOCOL.md`](PROTOCOL.md) — scientific scope and exact 530/8,420 design.
7. [`STATISTICAL_ANALYSIS_PLAN.md`](STATISTICAL_ANALYSIS_PLAN.md) — endpoints, paired analysis, multiplicity, and missingness.
8. [`COCO_DATA_SOURCE.md`](COCO_DATA_SOURCE.md) — frozen COCO 2017 CC BY 2.0 source and attribution policy.

## Frozen inputs

Canonical experiment bytes are stored directly in GitHub:

- 54 covers under `data/5j/coco2017/prepared/covers/`;
- 54 secrets under `data/5j/coco2017/prepared/secrets/`;
- exact source metadata, attribution, and SHA-256 inventory;
- 2 calibration pairs;
- 2 engineering dry-run pairs;
- 50 main pairs;
- 10 sweep pairs frozen as a subset of main.

Dataset materialization commit:

`2cb8bf926f6214d2e278296b32b00e9e2d3fe9f2`

`configs/5j/data_registry_v1.json` is `frozen`, `main_run_authorized=true`, and contains no data blockers.

## Implementation state

Implemented:

- exact 530/8,420 protocol and validators;
- format-v2 Base/Detail integrity and C3_NP;
- progressive payload and PSNR sweeps;
- failure-severity/ECC diagnostics;
- frozen B1/B2 baselines;
- seven-method local resumable dispatcher;
- 16-worker benchmark harness;
- path-independent calibration-only stability builder;
- automatic Octave/toolbox/Stage-0/stability binding freeze;
- one-command runtime-bound final-plan preparation;
- pair-level statistics, tables, figures, and final-only archive tooling.

## CI and logical-plan state

Relevant stale CI failures have been repaired. At commit
`19dcf3b40140802733b6161f475d5a0b111d8b06`, all reported 5J workflows
completed successfully. Runner-preflight run `31271680057` subsequently passed
the new runtime-freeze and path-independent stability tests.

Production logical execution-plan run `31271451804` succeeded with:

```text
plan_id = 06b512c1cb6e6e8e1d5c97ec68b6450552a49fa03378d421e5cd13e5953b212a
530 embeddings
8420 evaluations
```

This is intentionally **unbound**. The final scientific plan/run ID is produced only after the actual server runtime and real stability profile are hashed and validated.

## Remaining machine-dependent work

1. connect/check out the reviewed commit on the upgraded 32-CPU/64-GiB server;
2. generate the real PDFB stability profile from the two frozen calibration covers;
3. run `prepare_final_execution_plan.py` to create the runtime-bound final plan and run ID;
4. run the initial 16-worker benchmark and tune only from measured evidence;
5. run the two-pair seven-method engineering dry run;
6. execute all 530 embeddings and 8,420 evaluations;
7. generate analysis/manuscript outputs;
8. perform one final verified remote backup.

No FINAL-5J-v1 scientific run has occurred yet: 0/530 embeddings and 0/8,420 evaluations.

## Execution semantics

```text
planned → running → locally_complete
```

Remote backup does not block numerical execution or resume.

After the entire computation and publication package are complete:

```text
run_complete_local → one final archive → remote verification → project_archived
```
