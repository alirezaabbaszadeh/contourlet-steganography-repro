# FINAL-5J-v1 Implementation Index

Current authority and status:

1. `AUTHOR_DECISION_FINAL_BACKUP_ONLY.md` — one remote backup only after full completion.
2. `IMPLEMENTATION_CHECKPOINT_CI_PLAN_READY_20260808.md` — current CI/stability/final-plan checkpoint.
3. `IMPLEMENTATION_CHECKPOINT_DATASET_FROZEN_20260808.md` — frozen real COCO data checkpoint.
4. `RUNTIME_BINDING_AND_PLAN_FINALIZATION.md` — server finalization runbook.
5. `PROTOCOL.md` and `STATISTICAL_ANALYSIS_PLAN.md` — frozen science and analysis.

Ready in GitHub: frozen 54-pair dataset, frozen B1/B2, C0/C1/C2/C3_NP/C3, exact 530/8,420 task expansion, seven-method local resumable runner, 16-worker benchmark harness, failure-severity/reporting pipeline, path-independent PDFB stability builder, automatic runtime binding freeze, one-command final-plan preparation, and final-only archive tooling.

Relevant stale CI failures were repaired. All reported 5J workflows were successful at tested commit `19dcf3b40140802733b6161f475d5a0b111d8b06`. Runner-preflight run `31271680057` passed the new runtime-freeze and path-independent stability tests.

Production logical plan run `31271451804` succeeded:

```text
plan_id = 06b512c1cb6e6e8e1d5c97ec68b6450552a49fa03378d421e5cd13e5953b212a
530 embeddings / 8420 evaluations
```

This plan is intentionally unbound. The final scientific plan/run ID is produced on the target server after hashing the real Octave/PDFB runtime, toolbox, Stage-0 evidence, and real calibration stability profile.

Next:

```text
server checkout
→ real two-cover PDFB stability
→ prepare_final_execution_plan.py
→ 16-worker benchmark
→ two-pair seven-method dry run
→ full 530/8420 execution
→ analysis/manuscript
→ one final verified backup
```

No FINAL-5J-v1 scientific run has occurred yet: 0/530 embeddings and 0/8,420 evaluations.
