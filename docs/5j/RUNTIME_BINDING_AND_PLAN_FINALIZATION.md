# FINAL-5J runtime binding and plan finalization

Status: executable preflight contract  
Protocol: `FINAL-5J-v1`

## Why the plan has two stages

The logical execution plan freezes the scientific matrix: pairs, methods,
payload fractions, PSNR targets, channel instances, seeds, source tree,
configuration, and approved baseline contracts. It is not yet a scientific run
identity because the external PDFB environment can still change.

The finalized execution plan additionally binds:

- the Octave executable bytes;
- the complete Contourlet toolbox tree;
- the passing runtime-verified Stage-0 evidence;
- the calibration-only stability profile.

The SHA-256 of the frozen runtime-binding file enters every embedding and
evaluation identity. A one-byte change in any bound artifact requires a new
binding file, new task IDs, a new plan ID, and a new run ID.

## Required order

### 1. Build the logical plan

```bash
python scripts/5j/build_execution_plan.py \
  --repository-root . \
  --study-plan configs/5j/study_plan_v1.json \
  --seed-lock configs/5j/seeds.lock.json \
  --baseline-registry configs/5j/baseline_registry_v1.json \
  --config configs/5j/format_v2_layer_integrity.toml \
  --source-root src/ctsteg \
  --main-manifest data-manifests/5j/main_50_pairs.csv \
  --sweep-manifest data-manifests/5j/sweep_10_pairs.csv \
  --output /srv/ctsteg/plans/final-5j-unbound.json
```

The expected logical matrix is exactly:

- 530 embeddings;
- 8,420 evaluations;
- 8,950 durable task objects in total.

### 2. Freeze external runtime bindings

Start from `configs/5j/runtime_bindings_v1.template.json`. Fill the actual paths
and verified hashes, set `status` to `frozen`, set `science_ready` to `true`,
record the approver and approval time, and clear all blockers.

The binding validator requires:

- an executable regular runtime file;
- the exact toolbox tree hash and unique required toolbox functions;
- passing Stage-0 evidence with the approved profile and scheme;
- `exploratory=false` and `author_equivalence_claimed=false`;
- a calibration-only, transform-matched stability artifact.

### 3. Finalize and re-address the plan

```bash
python scripts/5j/finalize_execution_plan.py \
  --plan /srv/ctsteg/plans/final-5j-unbound.json \
  --runtime-bindings /etc/ctsteg/final-5j-runtime-bindings.json \
  --output /srv/ctsteg/plans/final-5j-bound.json \
  --verification-output /srv/ctsteg/plans/runtime-binding-verification.json \
  --json
```

This command re-hashes all 530 embedding tasks and all 8,420 evaluation tasks.
The original logical `plan_id` is retained as `base_plan_id` for traceability.

### 4. Run the fail-closed preflight

```bash
python scripts/5j/run_research.py \
  --plan /srv/ctsteg/plans/final-5j-bound.json \
  --runtime-bindings /etc/ctsteg/final-5j-runtime-bindings.json \
  --repository-root /opt/ctsteg/current \
  --science-ready-report /srv/ctsteg/gates/input-readiness.json \
  --output-root /srv/ctsteg/results \
  --cache-dir /srv/ctsteg/cache \
  --ledger /srv/ctsteg/backup/ledger.json \
  --json
```

The command re-verifies the bound runtime bytes and refuses an unbound plan. At
this implementation stage it publishes an immutable preflight/status directory
and records `preflight_passed_execution_blocked`; numerical dispatch remains
closed until the dedicated worker and B1/B2 adapters pass their own gates.

### 5. Reconstruct progress

```bash
python scripts/5j/research_status.py \
  --plan /srv/ctsteg/plans/final-5j-bound.json \
  --cache-dir /srv/ctsteg/cache \
  --ledger /srv/ctsteg/backup/ledger.json \
  --output /srv/ctsteg/results/status.json \
  --json
```

Progress is reconstructed from immutable cache objects and the backup ledger.
Only `committed_complete` objects count as durable completion. A locally valid
object without verified remote backup is reported as `backup_pending`.

## Prohibited shortcuts

- Do not execute the unbound logical plan.
- Do not edit a finalized plan.
- Do not replace a runtime-binding file in place after plan finalization.
- Do not reuse cached objects after a binding hash changes.
- Do not mark an object complete from local presence alone.
- Do not weaken Stage-0 or stability checks to make preflight pass.
