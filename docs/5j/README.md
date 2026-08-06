# FINAL-5J-v1 Implementation Index

This directory is the operational entry point for continuing 5J without chat history.

## Read first

1. [`../FINAL_5J_IMPLEMENTATION_PLAN.md`](../FINAL_5J_IMPLEMENTATION_PLAN.md) — complete programme and phase gates.
2. [`PROTOCOL.md`](PROTOCOL.md) — frozen scientific scope and exact 530/8,420 design.
3. [`STATISTICAL_ANALYSIS_PLAN.md`](STATISTICAL_ANALYSIS_PLAN.md) — preregistered endpoints, comparisons, aggregation, multiplicity, and missingness.
4. [`FAILURE_SEVERITY_SPEC.md`](FAILURE_SEVERITY_SPEC.md) — S0–S6 stages, ECC overload, recovery fractions, and comparative failure reporting.
5. [`SECURITY_BACKUP_POLICY.md`](SECURITY_BACKUP_POLICY.md) — plaintext-secret prohibition and remote-verified completion policy.

## Machine-readable authority

- Plan: [`../../configs/5j/study_plan_v1.json`](../../configs/5j/study_plan_v1.json)
- Schema: [`../../schemas/5j/study_plan.schema.json`](../../schemas/5j/study_plan.schema.json)
- Validator: [`../../scripts/5j/validate_protocol.py`](../../scripts/5j/validate_protocol.py)
- Planner: [`../../scripts/5j/plan_run.py`](../../scripts/5j/plan_run.py)
- CI: [`../../.github/workflows/5j-protocol-validation.yml`](../../.github/workflows/5j-protocol-validation.yml)
- Tracking issue: GitHub Issue #6

## Current implementation state

Completed in the first package:

- governance and backup policy;
- executable protocol and frozen counts;
- Statistical Analysis Plan baseline;
- comparative failure-severity contract;
- machine-readable study plan and schema;
- fail-closed validator and deterministic planner;
- protocol CI and basic plaintext-secret scan.

Still blocked:

- 50-pair manifest and data-rights inventory;
- attack seed lock;
- payload format v2 with independent Base/Detail integrity;
- C3_NP implementation;
- B1/B2 selection, license review, harmonization, and adapters;
- typed evaluation and backup-ledger schemas;
- remote backup upload/restore/evacuation implementation;
- dry run, pilot, main execution, analysis, and manuscript revision.

## Commands

```bash
python scripts/5j/validate_protocol.py
python scripts/5j/validate_protocol.py --json
python scripts/5j/plan_run.py
python scripts/5j/plan_run.py --json --output 5j-plan-summary.json
```

A valid plan must report:

```text
main_embeddings=350
main_evaluations=7700
payload_sweep_embeddings=90
payload_sweep_evaluations=360
psnr_sweep_embeddings=90
psnr_sweep_evaluations=360
total_embeddings=530
total_evaluations=8420
```

## Next implementation package

Proceed in this order:

1. pair-manifest and rights schemas;
2. data and baseline contract;
3. deterministic attack seed lock;
4. format-v2 design and corruption fixtures;
5. C3_NP single-factor implementation;
6. B1/B2 candidate review in parallel.

The scientific main run remains prohibited until all required gates in the machine-readable plan are true and remote backup verification is operational.
