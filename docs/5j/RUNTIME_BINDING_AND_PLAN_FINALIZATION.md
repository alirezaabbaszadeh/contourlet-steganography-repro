# FINAL-5J runtime binding and plan finalization

Status: executable server-finalization contract  
Protocol: `FINAL-5J-v1`

## Purpose

The scientific matrix is already frozen in GitHub: data bytes, B1/B2 contracts,
attack seeds, payload/PSNR sweeps, and the exact 530-embedding / 8,420-evaluation
logical task expansion.

The only machine-specific scientific inputs that cannot be frozen on GitHub CI
are the real PDFB runtime artifacts used on the numerical server:

- the Octave executable bytes;
- the complete Contourlet toolbox tree;
- passing runtime-verified Stage-0 evidence;
- the calibration-only stability profile generated with those exact runtime
  bytes and the two frozen calibration covers.

The final bound plan includes the verified runtime-binding hash in task identity.
It is the only plan accepted for the scientific server run.

## Current logical plan

GitHub Actions builds and validates the production logical plan directly from
frozen inputs. The required counts are exactly:

- 530 embeddings;
- 8,420 evaluations.

The logical plan is deliberately **unbound**. It is evidence that the study
matrix is complete and deterministic, but it is not yet the final server run
identity.

## Server-finalization sequence

### 1. Checkout the exact approved branch/commit

The server must consume the Git-tracked dataset and manifests. Do not reselect
or regenerate the study images.

### 2. Validate frozen inputs

```bash
python scripts/5j/validate_inputs.py \
  --check-files \
  --require-science-ready \
  --json
```

Expected manifest counts are 2 calibration, 2 dry-run, 50 main, and 10 sweep.

### 3. Build the real PDFB stability profile

Set the real runtime/toolbox environment required by the PDFB adapter, then run:

```bash
python scripts/5j/build_stability_profile.py \
  --repository-root /opt/ctsteg/current \
  --manifest /opt/ctsteg/current/data-manifests/5j/calibration.csv \
  --config /opt/ctsteg/current/configs/5j/format_v2_layer_integrity.toml \
  --output /srv/ctsteg/evidence/final-5j-stability.json
```

Only the two frozen calibration covers are used. The profile records
repository-relative scientific input paths plus exact hashes, so checkout path
alone does not change its scientific identity.

The command refuses to overwrite an existing non-empty profile.

### 4. Freeze runtime bindings and finalize the plan

No hand-editing of runtime hash JSON is required. Use the one-command finalizer:

```bash
python scripts/5j/prepare_final_execution_plan.py \
  --repository-root /opt/ctsteg/current \
  --runtime-executable /usr/bin/octave-cli \
  --toolbox /opt/ctsteg/toolboxes/contourlet-real \
  --stage0-evidence /srv/ctsteg/evidence/pdfb-stage0-final.json \
  --stability-profile /srv/ctsteg/evidence/final-5j-stability.json \
  --approved-by alirezaabbaszadeh \
  --output-dir /srv/ctsteg/finalization \
  --json
```

This command, in order:

1. revalidates all Git-tracked images and frozen input contracts;
2. builds the production logical 530/8,420 plan;
3. computes the actual Octave executable SHA-256;
4. inventories and hashes the complete Contourlet toolbox tree;
5. validates the locked Stage-0 contract;
6. validates the transform-matched calibration-only stability artifact;
7. writes and re-verifies the frozen runtime-binding file;
8. re-addresses all 530 embedding IDs and 8,420 evaluation IDs;
9. writes the final runtime-bound plan and independent verification reports.

Expected output directory:

```text
input-readiness.json
final-5j-unbound.json
final-5j-runtime-bindings.json
runtime-binding-verification.json
final-5j-bound.json
final-plan-verification.json
FINAL_PLAN_READY.json
```

All finalization outputs refuse destructive overwrite. Re-running after a failed
or superseded freeze should use a new empty output directory.

## Execution

The scientific dispatcher is already implemented for all seven methods:

```text
C0 / C1 / C2 / C3_NP / C3 / B1 / B2
```

Execution is intentionally simple:

```text
all embeddings
→ local hash/schema and clean-acceptance validation
→ all dependent evaluations
→ run_complete_local
```

The dispatcher uses the existing content-addressed cache, `DurableTaskRunner`,
`RunLock`, spawn-based process workers, event logs, and resume behavior.

Remote backup is **not** an execution dependency.

### Preflight

Before dispatch:

```bash
python scripts/5j/run_research.py \
  --plan /srv/ctsteg/finalization/final-5j-bound.json \
  --runtime-bindings /srv/ctsteg/finalization/final-5j-runtime-bindings.json \
  --repository-root /opt/ctsteg/current \
  --science-ready-report /srv/ctsteg/finalization/input-readiness.json \
  --output-root /srv/ctsteg/results \
  --cache-dir /srv/ctsteg/cache \
  --json
```

### Numerical dispatch

Use the local seven-method dispatcher with the final bound plan. Worker count
starts at 16 on the upgraded 32-CPU/64-GiB server and is adjusted only from
measured throughput/RAM/CPU/I/O evidence.

## Progress and resume semantics

During numerical execution:

```text
planned
→ running
→ locally_complete
```

A deep-validated content-store object counts as completed progress. A remote
backup or remote ledger is not required for the next scientific task to run.

A process interruption is handled by local content-addressed resume: valid
objects are reused; incomplete/failed attempts are not silently promoted to
complete objects.

## Final backup semantics

Only after computation, sweeps, analysis, tables, figures, manuscript,
supplement, logs, and inventories are locally complete:

```text
run_complete_local
→ one final archive
→ upload
→ independent remote hash verification
→ project_archived
```

This final-only rule supersedes older planning text that required per-object
remote verification during execution.

## Prohibited shortcuts

- Do not execute the unbound logical plan as the scientific run.
- Do not edit a finalized plan in place.
- Do not hand-enter runtime/toolbox/stability hashes.
- Do not reuse a final bound plan after runtime, toolbox, Stage-0, stability,
  source, frozen data, baseline, config, or seed identity changes.
- Do not build stability from main-study or sweep outcomes.
- Do not reselect or regenerate the frozen GitHub dataset on the server.
- Do not disable Stage-0, stability, input-hash, or clean-embedding gates merely
  to make execution proceed.
- Do not introduce remote-backup waiting into the numerical scheduler.
