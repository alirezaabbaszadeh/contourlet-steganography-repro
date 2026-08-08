# FINAL-5J-v1 Implementation Index

This directory is the operational entry point for continuing 5J without chat history.

## Read first

1. [`AUTHOR_DECISION_FINAL_BACKUP_ONLY.md`](AUTHOR_DECISION_FINAL_BACKUP_ONLY.md) — authoritative correction: remote backup occurs once after the entire run, analysis, and manuscript package are complete.
2. [`../FINAL_5J_IMPLEMENTATION_PLAN.md`](../FINAL_5J_IMPLEMENTATION_PLAN.md) — original comprehensive programme; backup statements conflicting with the author correction are superseded.
3. [`PROTOCOL.md`](PROTOCOL.md) — scientific scope and exact 530/8,420 design.
4. [`STATISTICAL_ANALYSIS_PLAN.md`](STATISTICAL_ANALYSIS_PLAN.md) — endpoints, comparisons, aggregation, multiplicity, and missingness.
5. [`FAILURE_SEVERITY_SPEC.md`](FAILURE_SEVERITY_SPEC.md) — S0–S6 stages, ECC overload, recovery fractions, and comparative failure reporting.
6. [`SECURITY_BACKUP_POLICY.md`](SECURITY_BACKUP_POLICY.md) — local execution reliability, secret prohibition, and one final verified archive.
7. [`DATA_AND_BASELINE_CONTRACT.md`](DATA_AND_BASELINE_CONTRACT.md) — pair provenance, rights, manifest freeze, and B1/B2 harmonization.
8. [`COCO_DATA_SOURCE.md`](COCO_DATA_SOURCE.md) — deterministic 108-image / 54-pair COCO 2017 CC BY 2.0 acquisition and preprocessing policy.

## Machine-readable authority

### Study design

- Plan: [`../../configs/5j/study_plan_v1.json`](../../configs/5j/study_plan_v1.json)
- Schema: [`../../schemas/5j/study_plan.schema.json`](../../schemas/5j/study_plan.schema.json)
- Validator: [`../../scripts/5j/validate_protocol.py`](../../scripts/5j/validate_protocol.py)
- Planner: [`../../scripts/5j/plan_run.py`](../../scripts/5j/plan_run.py)

### Inputs and baselines

- COCO bootstrap: [`../../scripts/5j/bootstrap_coco_data.py`](../../scripts/5j/bootstrap_coco_data.py)
- COCO candidate preparer: [`../../scripts/5j/prepare_coco_candidates.py`](../../scripts/5j/prepare_coco_candidates.py)
- Deterministic split freezer: [`../../scripts/5j/freeze_data_manifests.py`](../../scripts/5j/freeze_data_manifests.py)
- Data registry: [`../../configs/5j/data_registry_v1.json`](../../configs/5j/data_registry_v1.json)
- Baseline registry: [`../../configs/5j/baseline_registry_v1.json`](../../configs/5j/baseline_registry_v1.json)
- Attack seed lock: [`../../configs/5j/seeds.lock.json`](../../configs/5j/seeds.lock.json)
- Pair schema: [`../../schemas/5j/pair_manifest.schema.json`](../../schemas/5j/pair_manifest.schema.json)
- Baseline schema: [`../../schemas/5j/baseline_contract.schema.json`](../../schemas/5j/baseline_contract.schema.json)
- Input validator: [`../../scripts/5j/validate_inputs.py`](../../scripts/5j/validate_inputs.py)
- Manifest templates: [`../../data-manifests/5j/`](../../data-manifests/5j/)
- Tracking issue: GitHub Issue #6

## Current implementation state

Implemented:

- protocol and exact counts;
- format-v2 Base/Detail integrity;
- C3_NP ablation;
- progressive payload support;
- failure-severity diagnostics;
- B1/B2 canonical baselines, contracts, and code freeze;
- unified seven-method local worker;
- simple two-stage local-cache dispatcher and resume;
- 16-worker engineering benchmark harness;
- deterministic COCO 2017 CC BY 2.0 acquisition/preprocessing path for 108 unique source images -> 54 candidate pairs;
- deterministic calibration/dry-run/main/sweep manifest freezer;
- calibration-only stability builder;
- pair-level statistical analysis, tables, and figures;
- deterministic final-only archive and verifier.

Remaining external execution work:

- run the COCO bootstrap on a network-connected target environment and commit the resulting frozen manifest metadata/hashes;
- generate the real target-environment PDFB stability profile;
- finalize the execution plan after the final source/runtime freeze;
- obtain observable green CI or repair concrete workflow failures;
- run the 16-worker benchmark on the upgraded 32-CPU/64-GiB server;
- complete the two-pair engineering dry run;
- execute the main study and sweeps;
- generate analysis and manuscript outputs from real results;
- perform one final verified remote backup.

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

1. run `python scripts/5j/bootstrap_coco_data.py` on the target environment;
2. validate/freeze the resulting real manifests;
3. build the real PDFB stability profile;
4. finalize the execution plan;
5. run the 16-worker benchmark and two-pair engineering dry run;
6. execute the full study;
7. build analysis, tables, figures, and manuscript;
8. create and verify one final backup.
