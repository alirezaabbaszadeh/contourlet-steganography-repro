# FINAL-5J Handoff

1. Ferdowsi host: `c32`, endpoint `linux.ferdowsi.cloud:2258`, 32 CPU / 62.79 GiB RAM / ~100GB disk, swap 0.
2. Selected worker count is **20** from real 32c64g benchmark + fresh confirmation; do not force 29.
3. Last published scientific branch head before Issue #10 fix: `0005cba51a09ab0c062bfc4bd21a499fa501841c`; baseline freeze `FINAL-5J-BASELINES-v3` validates and its frozen files are unchanged by Issue #10.
4. Scientific checkout: `/srv/ctsteg/control/scientific-repo`; current local branch `agent/5j-internal-scientific-failure` contains Issue #10 fix work.
5. Production service `ctsteg-research@final.service` is STOPPED/INACTIVE. Do not restart the v2 plan.
6. Preserved v2 run: plan `b5bea8e4a3836347d0c9e0d75f0ecc5a01dd43a802a880093c9062ff156a8a45`, run `5j-b5bea8e4a3836347d0c9`; stopped deliberately at 421/530 embeddings, zero operational failures, zero restarts, zero evaluations.
7. B2 main results already observed in preserved v2: 32 clean-complete and 18 typed `clean_embedding_infeasible` scientific failures. No B2 parameter was changed.
8. Internal preregistered pair `coco-000000479126-000000199771` produced clean-decode scientific failures for several internal methods/operating points. GitHub issue #10 authorizes only typed result-materialization semantics, not algorithm/parameter changes.
9. Issue #10 implementation adds machine-readable internal clean failure metadata (`clean_decode_scientific_failure`, actual clean failure stage/validity/integrity, `prerequisite_unreachable=true`, `missingness=not_evaluated`), accepts only that typed shape at dispatcher stage acceptance, and materializes dependent evaluations without running attacks.
10. Real target-server probe on the problematic pair/C0 passed: embedding `S4_HEADER_FAILURE/header_failure`; dependent evaluation `scientific_failure`, `not_evaluated`, `attacked_sha256=null`.
11. Targeted tests, protocol/input validation, and baseline-freeze-v3 validation pass. Full suite runs 212 tests with only the same three historical failures (two C3_NP/format-v1 legacy errors + one factorial-comparison assertion).
12. Next: publish Issue #10 source commit atomically; create SHA-pinned external venv; fresh finalization/plan/run/cache/output namespace; preflight 0/8950; fresh seven-method dry run at 20 workers; private runtime_check and research_status 0/8950; update fixed service/helper/config to the new namespace; only then start new production and monitor full embedding/evaluation stages.
13. Preserve all previous failed/stopped namespaces. Do not mix them into the new run and do not perform remote per-object backup during computation.
