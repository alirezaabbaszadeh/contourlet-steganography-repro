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

## Machine-readable authority

### Study design

- Plan: [`../../configs/5j/study_plan_v1.json`](../../configs/5j/study_plan_v1.json)
- Schema: [`../../schemas/5j/study_plan.schema.json`](../../schemas/5j/study_plan.schema.json)
- Validator: [`../../scripts/5j/validate_protocol.py`](../../scripts/5j/validate_protocol.py)
- Planner: [`../../scripts/5j/plan_run.py`](../../scripts/5j/plan_run.py)

### Inputs and baselines

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
- content-addressed local worker and resume primitives;
- 16-worker engineering benchmark harness;
- final-archive tooling, now removed from the execution scheduling loop.

Primary unresolved work:

- select, license-review, implement, and test B1 and B2;
- freeze the real calibration, dry-run, main-50, and sweep-10 manifests;
- generate the real stability profile;
- complete a simple dependency-aware local-cache runner;
- run the engineering dry run;
- execute the main study and sweeps;
- generate analysis and manuscript outputs;
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

## Immediate implementation order

1. identify and implement B1/B2;
2. freeze real data manifests and seeds;
3. simplify and complete the local-cache runner;
4. run the two-pair engineering dry run with 16 workers;
5. execute the full study;
6. build analysis, tables, figures, and manuscript;
7. create and verify one final backup.
