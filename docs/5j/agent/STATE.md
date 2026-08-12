# FINAL-5J Agent State
updated_at_utc: 2026-08-12T13:31:00Z
repository: https://github.com/alirezaabbaszadeh/contourlet-steganography-repro
branch: agent/server-control-plane
base_published_head: 15a1896881500871653ca9584dfe5488f01ca089
scientific_commit: pending final publication checkpoint; src/ctsteg fingerprint unchanged from 15a1896
phase: WORKER_BENCHMARK
phase_status: passed_selected_worker_confirmation
plan_id: pending fresh 32c64g finalization after publication
run_id: pending fresh 32c64g finalization after publication
selected_workers: 20
embeddings_complete_scientific: 0
evaluations_complete_scientific: 0
active_process_or_service: none
host: c32; 32 logical CPUs; MemTotal 62.79 GiB; MemAvailable ~61 GiB idle; swap 0; root 96G total / 84G free; Octave 8.4.0; Python 3.12.3
worker_profile: ferdowsi-32c64g-100gb-v1; initial 16; scale 20 -> 24 -> 27 -> 29; fallback 12 -> 8 -> 4; hard cap 29; three CPUs reserved
worker_selection_evidence: 16=8927.46 t/h; 20=11866.56 t/h; 24=12739.26 t/h; 27=12101.07 t/h; 24 confirmation=11118.39 t/h (13.59% diff, rejected); 20 confirmation=10941.53 t/h (8.11% diff, passed)
last_successful_command: 20-worker fresh-cache confirmation completed 200/200 tasks with zero operational failures and selected_worker_confirmation_passed
last_failure: 24-worker repeatability gate exceeded frozen 10% threshold (13.59%); classified operational/performance, no scientific task affected
current_blockers: publish current orchestration/docs checkpoint; regenerate finalization for final published SHA; rerun seven-method engineering dry run with workers=20; install/validate durable final service; private runner still registered under historical label ctsteg-ferdowsi-8c16g but service is online
next_exact_command: publish current checkpoint, fetch exact published SHA into /srv/ctsteg/control/scientific-repo, regenerate FINAL-5J runtime-bound plan, then run fresh seven-method engineering dry run with workers=20 and hard-cap=29
next_acceptance_condition: published SHA tree-equal to server checkout; finalization/preflight pass; seven-method dry run completes 14/14 embeddings and 308/308 evaluations with zero operational failures
worktree_status: orchestration/docs checkpoint pending sync; no scientific execution started
