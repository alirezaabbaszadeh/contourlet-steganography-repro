# FINAL-5J-v1 Implementation Index

This directory is the operational entry point for continuing 5J without chat history.

## Read first

1. [`../FINAL_5J_IMPLEMENTATION_PLAN.md`](../FINAL_5J_IMPLEMENTATION_PLAN.md) — complete programme and phase gates.
2. [`PROTOCOL.md`](PROTOCOL.md) — frozen scientific scope and exact 530/8,420 design.
3. [`STATISTICAL_ANALYSIS_PLAN.md`](STATISTICAL_ANALYSIS_PLAN.md) — preregistered endpoints, comparisons, aggregation, multiplicity, and missingness.
4. [`FAILURE_SEVERITY_SPEC.md`](FAILURE_SEVERITY_SPEC.md) — S0–S6 stages, ECC overload, recovery fractions, and comparative failure reporting.
5. [`SECURITY_BACKUP_POLICY.md`](SECURITY_BACKUP_POLICY.md) — plaintext-secret prohibition and remote-verified completion policy.
6. [`DATA_AND_BASELINE_CONTRACT.md`](DATA_AND_BASELINE_CONTRACT.md) — pair provenance, rights, manifest freeze, and B1/B2 harmonization gates.

## Machine-readable authority

### Study design

- Plan: [`../../configs/5j/study_plan_v1.json`](../../configs/5j/study_plan_v1.json)
- Schema: [`../../schemas/5j/study_plan.schema.json`](../../schemas/5j/study_plan.schema.json)
- Validator: [`../../scripts/5j/validate_protocol.py`](../../scripts/5j/validate_protocol.py)
- Planner: [`../../scripts/5j/plan_run.py`](../../scripts/5j/plan_run.py)
- CI: [`../../.github/workflows/5j-protocol-validation.yml`](../../.github/workflows/5j-protocol-validation.yml)

### Inputs and external baselines

- Data registry: [`../../configs/5j/data_registry_v1.json`](../../configs/5j/data_registry_v1.json)
- Baseline registry: [`../../configs/5j/baseline_registry_v1.json`](../../configs/5j/baseline_registry_v1.json)
- Attack seed lock: [`../../configs/5j/seeds.lock.json`](../../configs/5j/seeds.lock.json)
- Pair-row schema: [`../../schemas/5j/pair_manifest.schema.json`](../../schemas/5j/pair_manifest.schema.json)
- Baseline schema: [`../../schemas/5j/baseline_contract.schema.json`](../../schemas/5j/baseline_contract.schema.json)
- Input validator: [`../../scripts/5j/validate_inputs.py`](../../scripts/5j/validate_inputs.py)
- Manifest templates: [`../../data-manifests/5j/`](../../data-manifests/5j/)
- Input CI: [`../../.github/workflows/5j-input-validation.yml`](../../.github/workflows/5j-input-validation.yml)
- Tracking issue: GitHub Issue #6

## Current implementation state

Completed:

- governance and backup policy;
- executable protocol and frozen counts;
- Statistical Analysis Plan baseline;
- comparative failure-severity contract;
- machine-readable study plan and schema;
- fail-closed protocol validator and deterministic planner;
- pair-manifest columns, provenance, rights, and disjointness contract;
- calibration, dry-run, main-50, and sweep-10 CSV templates;
- B1/B2 machine-readable pending contracts and approval rules;
- 22-instance deterministic attack seed lock;
- input-readiness validator with an explicit `science_ready` gate;
- protocol and input GitHub Actions checks.

Still blocked:

- actual calibration and dry-run pair manifests;
- frozen 50-pair main manifest and 10-pair sweep subset;
- final rights inventory and verified encrypted private-input archive;
- payload format v2 with independent Base/Detail integrity;
- C3_NP implementation;
- B1/B2 candidate selection, license review, harmonization, and adapters;
- typed evaluation and backup-ledger schemas;
- remote backup upload/restore/evacuation implementation;
- dry run, pilot, main execution, analysis, and manuscript revision.

## Commands

```bash
python scripts/5j/validate_protocol.py
python scripts/5j/validate_protocol.py --json
python scripts/5j/plan_run.py
python scripts/5j/plan_run.py --json --output 5j-plan-summary.json

python scripts/5j/validate_inputs.py
python scripts/5j/validate_inputs.py --json
python scripts/5j/validate_inputs.py --require-science-ready
python scripts/5j/validate_inputs.py --check-files --require-science-ready
```

The normal input validation command must pass the implementation scaffolding while reporting `science_ready=false`. The `--require-science-ready` command must continue to fail until final manifests and both baseline approvals are complete.

A valid study plan must report:

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

1. specify payload format v2 and independent Base/Detail integrity;
2. add corruption fixtures and false-validity tests;
3. implement C3_NP as a single-factor placement ablation;
4. start evidence-based B1/B2 candidate review in parallel;
5. add typed embedding/evaluation/failure schemas;
6. implement the remote-verified backup ledger.

The scientific main run remains prohibited until all required gates in the machine-readable plan are true and remote backup verification is operational.
