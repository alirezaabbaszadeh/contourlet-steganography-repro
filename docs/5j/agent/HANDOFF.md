# FINAL-5J Handoff
1. Ferdowsi endpoint: `linux.ferdowsi.cloud:2258`; host `c32`; 32 CPU / 62.79 GiB RAM / ~100GB disk; swap 0.
2. Scientific checkout: `/srv/ctsteg/control/scientific-repo`.
3. Last published SHA: `f091d5a8fffeaa89bb9f00040420574674777ef6`; current local branch contains uncommitted correction work.
4. Production service `ctsteg-research@final.service` is STOPPED. Do not start it until a new plan/run is frozen.
5. Worker autotuning is complete: selected and fresh-confirmed `20` workers. Do not force 29.
6. Prior failed production namespace is immutable evidence: output `/srv/ctsteg/results/final-5j-32c64g-v1`, cache `/srv/ctsteg/cache/final5j-production-32c64g-v1`, run `5j-e9d4bebdd15f6f99c8ba`.
7. Failure root cause A: main plan internal method fingerprint used newline JSON; worker uses provenance JSON. Fix is only the internal method fingerprint function in `scripts/5j/build_execution_plan.py`.
8. Failure root cause B: six B2 main pairs have no clean-valid candidate under the unchanged frozen delta/four-pass contract. GitHub issue #9 authorizes typed scientific prerequisite-failure handling, not parameter tuning.
9. New baseline worker semantics commit `scientific_failure` embedding objects for exact clean-candidate exhaustion and `scientific_failure/S5/not_evaluated` dependent evaluation objects; unrelated exceptions remain operational failures.
10. Targeted regression tests and one real failed B2 pair probe passed locally using `PYTHONPATH=src` with the f091 dependency venv.
11. Next: run broad/full tests; publish implementation/protocol commit; generate `FINAL-5J-BASELINES-v3` pointing to that implementation commit; publish freeze commit; create a NEW SHA-bound external venv; regenerate finalization; fresh 20-worker seven-method dry run; private runtime/status gates; only then install updated service wrapper/config and start new production.
12. Preserve final-only backup policy; no remote backup during computation.
