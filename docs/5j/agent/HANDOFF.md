# FINAL-5J Handoff
1. Server checkout: `/home/ubuntu/contourlet-steganography-repro-github`.
2. Target host verified: `cpu8`, 8 logical CPUs, 16-GB class RAM (`MemTotal: 16375624 kB`), 96G root filesystem with 85G free, Python 3.12.3, Octave 8.4.0.
3. Windows VPN was the cause of the temporary SSH banner timeout. With VPN disabled, `linux.ferdowsi.cloud:2220` is reachable again.
4. Historical in-progress implementation was preserved first as local safety commit `83b44294542d9b5dc0b1ddaf84c9c1a51691cfec`.
5. The tested 8c/16G/100G host-retune line was integrated with that WIP. Public self-hosted server-control workflow remains deleted; private-control template is self-contained.
6. Worker profile is `ferdowsi-8c16g-100gb-v2`: start 4; unsafe fallback 2 then 1; test 6 only after stable 4; test 7 only after stable/materially faster 6; hard cap 7; one CPU reserved; zero tolerated swap I/O; 3-GiB memory floor; 30-GiB free-storage floor.
7. Engineering worker runner preserves ordered benchmark history and fresh-cache namespaces; the selected winner requires one fresh-cache confirmation.
8. Two-pair engineering dry-run orchestration covers all seven methods and 22 channels in an engineering-only namespace.
9. Manuscript workflow is current FINAL-5J/current-branch aware and no longer archive/old-branch driven.
10. A repository `.venv` was created on the server and the project installed editable with scientific Python dependencies.
11. Targeted post-merge validation passed: 12 worker-tuning + 39 control + 5 worker-trial + 3 dispatcher + 2 engineering-dry-run + 1 manuscript = 62 tests.
12. Full suite: 201 tests run; 197 pass, 1 optional PyArrow test skipped, 3 fail. The exact same three failures reproduce on base commit `53e8530`, so they are pre-existing legacy failures, not this integration regression.
13. No FINAL-5J scientific task has executed: counters remain 0/530 embeddings and 0/8420 evaluations.
14. Next: commit/publish integration, validate FINAL-5J input/runtime/toolbox readiness, build runtime bindings/finalized plan, then run engineering worker benchmark 4 -> 6 -> possibly 7 according to frozen gates.

17. Worker benchmark is complete and frozen selection is **4 workers**; 6/7 were not authorized because mean CPU busy remained below the preregistered 70% scale-up threshold.
18. Fresh seven-method dry run after the B2 repair amendment completed 14/14 embeddings and 308/308 evaluations with zero operational failures.
19. Baseline freeze v1 now fails by design because B2 source/contract changed before production; create `FINAL-5J-BASELINES-v2` only after the implementation SHA is published to GitHub.
20. Existing finalization v1/v2 directories are evidence only and stale after source changes; regenerate a new finalization directory after the final GitHub freeze commit.
