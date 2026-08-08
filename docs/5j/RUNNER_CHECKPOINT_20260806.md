# FINAL-5J runner checkpoint — 2026-08-06

Protocol: `FINAL-5J-v1`  
Branch: `agent/runtime-resume-gate`  
Checkpoint head before this file: `76d203a575f14fccb798cb4b70f758e0416bb2ce`

## Implemented in this checkpoint

### Runtime-bound scientific identity

The execution plan now has two explicit stages:

1. `scripts/5j/build_execution_plan.py` creates the logical 530/8,420 plan.
2. `scripts/5j/finalize_execution_plan.py` freezes the external PDFB runtime,
   toolbox tree, Stage-0 evidence, and calibration stability artifact into every
   task identity.

The finalization stage recomputes all 530 embedding IDs, all 8,420 evaluation
IDs, the plan ID, and the run ID. The logical plan ID is preserved as
`base_plan_id`.

Relevant files:

- `schemas/5j/runtime_bindings.schema.json`
- `configs/5j/runtime_bindings_v1.template.json`
- `src/ctsteg/digital_ad/runtime_bindings_5j.py`
- `scripts/5j/finalize_execution_plan.py`
- `docs/5j/RUNTIME_BINDING_AND_PLAN_FINALIZATION.md`

### Fail-closed preflight and status reconstruction

`src/ctsteg/digital_ad/runtime_5j.py` validates the complete plan identity,
source and input fingerprints, science-ready gate, immutable cache state, and
optional backup ledger. It reconstructs these operational states:

- `planned`
- `operational_failure`
- `backup_pending`
- `committed_complete`

Only remote-verified `committed_complete` objects count as durable progress.

Commands:

- `scripts/5j/run_research.py`
- `scripts/5j/research_status.py`

The main preflight still records `preflight_passed_execution_blocked` because a
multi-stage dispatcher and approved B1/B2 adapters are not yet complete.

### Resumable internal numerical worker

The five internal methods now have a durable worker:

- C0
- C1
- C2
- C3_NP
- C3

The worker:

- verifies input/config/stability hashes again inside the task;
- commits scientific failures as valid evidence;
- preserves operational failures as `FAILED.json` attempts;
- stores stego, protected stream, coefficient map, realized configuration,
  metrics, failure-severity diagnostics, timing, provenance, and images;
- reuses an object only after deep content-store verification;
- rejects B1/B2 dispatch until approved adapters exist.

Relevant files:

- `src/ctsteg/digital_ad/runtime_tasks_5j.py`
- `src/ctsteg/digital_ad/runtime_worker_5j.py`
- `scripts/5j/run_internal_task.py`
- `tests/test_5j_internal_worker.py`
- `.github/workflows/5j-internal-worker.yml`

### Failure-severity correctness fix

Two implementation defects were found during static review and corrected in
`failure_severity.py`:

1. `RSProfile.validate()` was called although the profile type exposes no such
   method.
2. raw layer length was incorrectly compared with padded RS input capacity.

Diagnostics now validate the profile locally and require:

```text
raw_reference_bytes = profile.input_bytes - profile.padding_bytes
```

This is necessary for all symmetric and unequal-protection profiles.

### Direct extraction compatibility

`pipeline.extract()` can again operate without an `expected_bits` reference. It
derives the protected stream length from method plus payload fraction and leaves
raw BER unavailable (`NaN`) while still performing valid extraction and decode.

## Tests and workflows added

- `tests/test_5j_runner_preflight.py`
- `tests/test_5j_runtime_bindings.py`
- `tests/test_5j_extract_compatibility.py`
- `tests/test_5j_internal_worker.py`
- `.github/workflows/5j-runner-preflight.yml`
- `.github/workflows/5j-internal-worker.yml`

## Verification status

GitHub Actions had not produced a workflow run for head
`76d203a575f14fccb798cb4b70f758e0416bb2ce` when checked. Therefore the new
runner, runtime-binding, extraction, and worker tests are **not yet claimed to be
CI-passing**.

Earlier workflow jobs also remained queued. This is tracked as CI verification
pending, not as scientific acceptance.

## Remaining hard blockers

1. Run and inspect all new CI jobs; fix any code-level failures.
2. Freeze the real 50-pair manifest and rights inventory.
3. Freeze the real 10-pair sweep subset.
4. Select, implement, license-review, clean-test, and approve B1/B2 adapters.
5. Produce a real frozen runtime-binding file on the target server.
6. Produce the calibration-only stability profile without using the 50 main
   pairs.
7. Implement the stage dispatcher that schedules embeddings before dependent
   evaluations and pauses for backup acknowledgement.
8. Complete engineering dry run, five-pair pilot, then the scientific run.

## Next implementation unit

After CI verification, implement `runtime_dispatch_5j.py` with dependency-aware
stages:

1. selected embedding tasks;
2. local validation;
3. backup upload and remote verification;
4. dependent evaluation tasks;
5. backup acknowledgement;
6. status/report reconstruction.

The dispatcher must consume only a finalized plan and must never synthesize new
tasks from observed results.
