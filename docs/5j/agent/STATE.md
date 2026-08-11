# FINAL-5J Agent State
updated_at_utc: 2026-08-11T17:50:00Z
repository: https://github.com/alirezaabbaszadeh/contourlet-steganography-repro
branch: agent/server-wip-preserve-20260811
base_head: 53e8530a76c55936a3e350555ec1df4a8ca536ee
scientific_commit: null
phase: SCIENTIFIC_COMMIT_FREEZE
phase_status: implementation_ready_for_publication_and_baseline_refreeze
plan_id: null
run_id: null
selected_workers: 4
embeddings_complete: 0
evaluations_complete: 0
active_process_or_service: none
host: cpu8; 8 logical CPUs; MemTotal 16375624 kB; root /dev/vda1 96G total / 85G free; Octave 8.4.0; Python 3.12.3
worker_profile: ferdowsi-8c16g-100gb-v2; ladder 4 -> 6 -> 7 when safe; fallback 4 -> 2 -> 1; hard cap 7; one CPU reserved
python_environment: repository .venv with editable project install; numpy 2.5.2; scipy 1.18.0; Pillow 12.3.0
last_successful_command: seven-method engineering dry run completed 14/14 embeddings and 308/308 evaluations with zero operational failures
last_verified_artifact: worker count 4 confirmed across two 200-task fresh-cache trials (0.234% throughput difference); seven-method dry run completed locally with 14/14 embeddings and 308/308 evaluations, zero operational failures
preexisting_full_suite_failures: test_all_four_bitstreams_are_exact_and_deterministic; test_manifest_benchmark_and_factorial_report; test_factorial_aggregates_repeated_seeds_within_pair
network_note: Windows VPN caused WSL-to-Ferdowsi SSH banner timeout; after VPN was disabled SSH on linux.ferdowsi.cloud:2220 returned immediately
current_blockers: GitHub publication of integrated implementation; baseline code freeze v1 is intentionally stale after pre-production B2 repair amendment and must become v2; private control runner/bootstrap absent; final runtime-bound plan must be regenerated after the final published/frozen source commit
next_exact_command: publish integrated implementation to agent/server-control-plane; create and validate FINAL-5J-BASELINES-v2 against the published implementation SHA; publish freeze commit; regenerate finalization and preflight against that exact final SHA
next_acceptance_condition: GitHub implementation/freeze commits published and tree-equal to server checkout; baseline freeze v2 validates; finalization/preflight regenerated; private control-plane requirement resolved before scientific execution
worktree_status: clean local integration commit; .venv ignored; no scientific execution started
