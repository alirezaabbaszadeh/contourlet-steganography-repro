# FINAL-5J Blockers

## Active
1. Complete and publish GitHub issue #10 internal clean-prerequisite result-materialization fix.
2. Verify `FINAL-5J-BASELINES-v3` remains valid without any frozen baseline-file change.
3. Create a new SHA-pinned external venv, finalization, plan/run ID, production cache/output namespace, and pass preflight.
4. Re-run fresh seven-method dry run at selected_workers=20.
5. Re-run private control runtime_check and require research_status=0/8950 before production restart.

## Preserved evidence
- Previous f091/e9d4 failed attempt remains immutable.
- Corrected 0005cba/b5bea8 v2 attempt remains immutable and will not be resumed after source changes. It stopped at 421/530 embeddings with zero operational failures and no evaluations.
- B2 main outcome observed in v2: 32 clean-complete, 18 typed clean-infeasible scientific failures under unchanged baseline parameters.
- Internal clean-decode scientific failures were observed on preregistered pair `coco-000000479126-000000199771`; no parameter or pair substitution is authorized.
