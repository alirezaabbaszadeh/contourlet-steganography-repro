# FINAL-5J-v1 checkpoint: CI clean and server finalization ready

Date: 2026-08-08  
Branch: `agent/runtime-resume-gate`  
Protocol: `FINAL-5J-v1`

## Summary

The repository-side work for the three immediate gates is now complete as far as
it can be completed without executing the real Octave/PDFB environment on the
numerical server.

Current state:

```text
PDFB stability implementation/validation path   READY
Real target PDFB stability numbers              SERVER EXECUTION REQUIRED
Relevant 5J CI cleanup                           COMPLETE
Production logical execution plan               COMPLETE
Runtime-bound final execution plan tooling       COMPLETE
Runtime-bound final plan bytes / run ID          SERVER EXECUTION REQUIRED
```

No FINAL-5J-v1 scientific embedding/evaluation has run yet.

## 1. Relevant CI cleanup

The stale CI assumptions introduced during earlier implementation were removed:

- input-readiness CI now expects the actually frozen and science-ready data and
  B1/B2 contracts;
- execution-plan CI now builds the real production logical plan instead of
  expecting production planning to fail;
- the analysis fixture permits statistically valid zero-width bootstrap
  intervals when all paired effects are identical;
- the final-archive workflow installs its test dependencies;
- secret-guard fixtures/scanners construct test private-key markers at runtime
  so the repository secret guard does not falsely flag its own safety tests.

At commit `19dcf3b40140802733b6161f475d5a0b111d8b06`, all reported 5J workflows
completed successfully, including:

- protocol validation;
- input readiness;
- execution plan;
- runner preflight;
- worker trial harness;
- baselines and local dispatcher;
- final-only archive;
- data preparation;
- internal worker;
- analysis and reporting;
- format-v2 core;
- backup-ledger validation tests;
- COCO materialization.

After adding the automatic runtime freezer/finalization commands, runner-preflight
run `31271680057` also completed successfully and explicitly passed:

- execution-plan contract tests;
- preflight/status tests;
- runtime-binding finalization tests;
- automatic runtime-binding freeze test;
- path-independent stability-artifact test.

Some workflows may be retriggered by later documentation/operator-command
commits. A queued duplicate does not invalidate the successful check for the
same relevant code path; nevertheless server execution should still use a
specific reviewed commit SHA.

## 2. Production logical execution plan

The repository now builds the real frozen logical plan in GitHub Actions from:

- the 50-pair main manifest;
- the 10-pair sweep subset;
- B1/B2 frozen contracts;
- the attack seed lock;
- the format-v2 configuration;
- the current `src/ctsteg` source fingerprint.

Successful execution-plan run: `31271451804`.

Logical plan identity from that run:

```text
plan_id = 06b512c1cb6e6e8e1d5c97ec68b6450552a49fa03378d421e5cd13e5953b212a
run_id  = 5j-06b512c1cb6e6e8e1d5c
```

Exact expanded counts:

```text
main                 350 embeddings / 7700 evaluations
payload sweep          90 embeddings /  360 evaluations
PSNR sweep             90 embeddings /  360 evaluations
TOTAL                  530 embeddings / 8420 evaluations
```

The workflow verified uniqueness of all 530 embedding IDs and all 8,420
evaluation IDs and uploaded `final-5j-unbound-execution-plan` as an Actions
artifact.

This logical plan is intentionally unbound. Its run ID is not the final
scientific run ID because the actual numerical PDFB runtime has not yet been
bound.

## 3. PDFB stability profile

The stability builder is implemented and tested:

- `scripts/5j/build_stability_profile.py`
- `tests/test_5j_stability_builder.py`

It requires exactly the two frozen calibration pairs and verifies their SHA-256
before calibration. It now records scientific paths repository-relative, so the
same Git-tracked bytes do not receive a different profile identity merely
because a checkout lives under a different absolute server directory.

The real stability values cannot be truthfully produced by GitHub CI because
they must come from the actual target Octave/PDFB runtime and Contourlet toolbox.
They must be produced once on the numerical server before the scientific run.

Expected command:

```bash
python scripts/5j/build_stability_profile.py \
  --repository-root /opt/ctsteg/current \
  --manifest /opt/ctsteg/current/data-manifests/5j/calibration.csv \
  --config /opt/ctsteg/current/configs/5j/format_v2_layer_integrity.toml \
  --output /srv/ctsteg/evidence/final-5j-stability.json
```

## 4. Automatic runtime binding freeze

New command:

`python scripts/5j/freeze_runtime_bindings.py`

It removes manual hash entry from the process. It computes and verifies:

- executable Octave SHA-256;
- complete Contourlet toolbox inventory/tree SHA-256;
- Stage-0 evidence SHA-256 and semantic contract;
- stability-profile SHA-256 and transform contract.

It writes a frozen science-ready binding only after all validations pass and
refuses to overwrite an existing non-empty binding.

The automatic freezer has an executable CI fixture test.

## 5. One-command final execution-plan preparation

New operator command:

`python scripts/5j/prepare_final_execution_plan.py`

Given the real server runtime paths and already-built stability profile, it:

1. verifies every frozen Git input and exact image hash;
2. builds the production 530/8,420 logical plan;
3. freezes real runtime/toolbox/Stage-0/stability hashes;
4. verifies the frozen runtime binding;
5. re-addresses all embedding and evaluation objects;
6. writes the final runtime-bound plan;
7. writes independent verification reports and `FINAL_PLAN_READY.json`.

Expected invocation:

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

Expected finalization directory:

```text
input-readiness.json
final-5j-unbound.json
final-5j-runtime-bindings.json
runtime-binding-verification.json
final-5j-bound.json
final-plan-verification.json
FINAL_PLAN_READY.json
```

The `plan_id` and `run_id` in `final-5j-bound.json` become the scientific run
identity. They cannot be known before the real runtime-binding/stability hash is
available and therefore must not be fabricated in repository CI.

## 6. Preflight status corrected

`run_research.py` now publishes:

```text
status = preflight_passed
execution_backend = seven_method_local_dispatcher
backup_policy = final_only_after_run_completion
```

The old `preflight_passed_execution_blocked` label was stale because the
seven-method dispatcher is already implemented.

## 7. Immediate server sequence

```text
checkout reviewed Git commit
→ verify 32 CPU / 64 GiB environment and Octave/PDFB paths
→ build real two-cover PDFB stability profile
→ prepare_final_execution_plan.py
→ fail-closed preflight
→ 16-worker benchmark
→ choose fastest stable worker count
→ two-pair seven-method engineering dry run
→ full FINAL-5J-v1 execution
```

Remote backup remains a single final-project operation and is not part of any
of these numerical execution gates.
