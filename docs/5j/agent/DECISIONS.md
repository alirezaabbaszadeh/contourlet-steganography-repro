# FINAL-5J Decisions

## 2026-08-11T16:22:10Z — Orientation authority and execution boundary
- Repository is fixed to `alirezaabbaszadeh/contourlet-steganography-repro`.
- Working branch is fixed to `agent/server-control-plane` at initial orientation HEAD `53e8530a76c55936a3e350555ec1df4a8ca536ee`.
- Historical server repositories and historical run metrics are not completion gates for FINAL-5J.
- No scientific task may run before the documented state machine gates are passed.
- No proxy may substitute for failed real PDFB evidence.
- Scientific commit remains unset until implementation fixes and CI validation are complete.

## 2026-08-11T16:32:59Z — Authority resolutions after full orientation reading
- `AUTHOR_DECISION_FINAL_BACKUP_ONLY.md` and `SECURITY_BACKUP_POLICY.md` supersede historical per-object remote-backup gates in `FINAL_5J_IMPLEMENTATION_PLAN.md` and old runner checkpoints.
- The 48-vCPU server-control design and the latest author operating contract expose the old 32CPU/64GiB worker profile as stale; no benchmark result can authorize science until a reviewed 48CPU profile is committed, or an explicit author decision retains the old cap.
- No decision is yet made to accept the public-repository self-hosted workflow; it conflicts with the approved private-control-repository design and remains a GAP_AUDIT blocker.

## 2026-08-11 — Current Ferdowsi host supersedes the planned 48-vCPU profile
- Author explicitly selected the currently provisioned 8-core / 16-GB / 100-GB server as the execution target.
- The active worker profile is therefore `ferdowsi-8c16g-100gb-v2`; historical 32/64 and planned 48/124 worker profiles are not execution authority for this run.
- Worker tuning starts at 4, may fall back to 2 then 1, may scale to 6 after safety gates, and may scale to 7 only after a stable 6-worker result with the locked gain/headroom gates. No count above 7 is permitted.
- One logical CPU remains reserved; every numerical worker remains internally single-threaded.

## 2026-08-11 — VPN incident classification
- The temporary `Connection timed out during banner exchange` was caused by the Windows VPN/network path, not the Ferdowsi private key or server SSH configuration. Disabling the VPN restored the same endpoint immediately.
- SSH timeout during that incident is not evidence that the VM was powered off and must not trigger destructive recovery or shutdown actions.

## 2026-08-11 — Validation interpretation
- The integrated implementation passes all 62 targeted tests relevant to worker tuning, control plane, trial runner, seven-method dispatcher/dry-run, and manuscript workflow.
- Three failures from the 201-test full suite reproduce identically on base commit `53e8530`; they are retained as pre-existing legacy test debt and are not classified as regressions of this implementation.

## 2026-08-11 — Worker benchmark acceptance
- Two fresh-cache engineering trials at 4 workers each completed 200/200 tasks with zero operational failures, OOM events, or swap I/O.
- Throughputs were 2923.905 and 2930.763 tasks/hour; repeat difference was 0.234257%.
- Mean CPU busy was about 47.6-48.1%, below the preregistered 70% scale-up gate. The frozen decision therefore accepts 4 workers and does not authorize post-hoc 6/7 trials.

## 2026-08-11 — Seven-method dry-run and B2 pre-production amendment
- The required two-pair dry run first exposed two orchestration defects (manifest-relative path resolution and internal method fingerprint canonicalization) and one B2 clean-round-trip defect. All failures were engineering-only and occurred before any 530/8420 scientific task.
- B2 repair was corrected within the existing contract boundaries: the frozen delta list, capacity, payload, selection rule, and four-pass maximum are unchanged; repair now corrects measured spatial-round-trip DCT residuals to the nearest desired-parity QIM lattice point.
- After fixes, a fresh dry-run completed 14/14 embeddings and 308/308 evaluations with zero operational failures. Attack-induced scientific failures remain valid engineering observations, not infrastructure failures.
- Because B2 source/contract bytes changed, `FINAL-5J-BASELINES-v1` is intentionally stale and a new v2 freeze is mandatory before production.
