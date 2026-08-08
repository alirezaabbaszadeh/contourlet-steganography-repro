# FINAL-5J-v1 Implementation Index

See `IMPLEMENTATION_CHECKPOINT_CI_PLAN_READY_20260808.md` for the current CI/stability/final-plan checkpoint and `IMPLEMENTATION_CHECKPOINT_DATASET_FROZEN_20260808.md` for the frozen dataset checkpoint.

Current scientific target: 530 embeddings / 8,420 evaluations. The frozen GitHub dataset and B1/B2 baselines are ready; relevant 5J CI has been repaired; the production logical plan is validated. The final runtime-bound plan is created on the target server after generating the real PDFB stability profile from the two frozen calibration covers.

Execution uses local resumable cache objects. Remote backup occurs once after the complete numerical and publication package is locally finished.
