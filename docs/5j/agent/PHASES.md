# FINAL-5J Phase Machine

Only one phase may be in progress. No scientific execution before all prior gates pass.

| Phase | Status | Required input | Core actions | Acceptance / artifact | Stop reasons |
|---|---|---|---|---|---|
| ORIENTATION | passed | pinned branch, clean starting worktree | inventory, full required reading, map control plane and algorithm entrypoints | reading ledger + state + handoff | missing/contradictory authority |
| GAP_AUDIT | passed | ORIENTATION passed | compare protocol/schema/tests/runtime/control-plane | recorded gap list and decisions | unresolved protocol conflict |
| IMPLEMENTATION_FIXES | passed | approved gap resolutions | smallest code/config/test fixes | tested implementation commit | numerical uncertainty |
| CI_VALIDATION | passed_with_known_legacy_debt | implementation checkpoint | pytest + protocol/baseline validation + CI | green CI evidence | failing test/CI |
| SCIENTIFIC_COMMIT_FREEZE | pending | green implementation commit | pin immutable SHA | SCIENTIFIC_COMMIT | remote divergence |
| SERVER_HEALTH | passed | pinned SHA | runner/CPU/RAM/swap/disk/services health | verified health report | host mismatch |
| INPUT_VALIDATION | pending | frozen Git inputs | validate files/hashes/splits/seeds/baselines | science-ready input report | any invalid frozen input |
| PDFB_STABILITY | pending | valid calibration inputs + real runtime | real Stage-0 + 2-pair stability | validated evidence JSON | PDFB/capacity/reconstruction failure |
| RUNTIME_BINDING | pending | real runtime evidence | build and independently verify bound plan | FINAL_PLAN_READY + plan_id/run_id | unbound/stale paths |
| WORKER_BENCHMARK | pending | bound plan | benchmark from 4 workers; conditionally test 6 then 7 | selected_workers + evidence | RAM/I/O/operational errors |
| SEVEN_METHOD_DRY_RUN | pending | benchmark winner | 2 external pairs, 7 methods, kill/resume/cache/schema | dry-run evidence excluded from science | B1/B2/resume failure |
| FULL_EXECUTION | pending | all gates passed | 530 embeddings + 8420 evaluations | 8950 tasks accounted | operational/protocol defect |
| ANALYSIS | pending | complete classified task set | preregistered analysis | analysis.json | incomplete accounting |
| MANUSCRIPT | pending | generated analysis | generated tables/figures + LaTeX builds | PDFs | manual-number contamination |
| FINAL_ARCHIVE | pending | publication artifacts | archive + independent verify + backup/hash verify | archive SHA256 + backup evidence | backup unverified |
| GITHUB_PUBLICATION | pending | verified archive/public artifacts | safe commits/push, no secrets/cache | remote branch/PR | remote ahead/conflict |
| COMPLETE | pending | all prior phases passed | final state/handoff/worktree clean | final report | any unfinished gate |
