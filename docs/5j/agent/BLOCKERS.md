# FINAL-5J Blockers

## Active blockers
1. `publication`: the resolved server integration still needs its merge commit published to GitHub before it can become a reviewed scientific source commit.
2. `environment/control_plane`: the approved private repository-scoped GitHub Actions runner/control checkout is not yet bootstrapped on the server.
3. `runtime_finalization`: FINAL-5J runtime bindings, calibration stability profile, bound plan and `FINAL_PLAN_READY.json` have not yet been regenerated against the final reviewed source commit and this server runtime/toolbox identity.
4. `performance_gate`: no 8c/16G/100G engineering benchmark has yet been measured. The first allowed trial is 4 workers; 6 and 7 are conditional on the frozen safety/throughput gates.

## Known non-blocking historical test debt
- Three full-suite failures reproduce unchanged on base `53e8530`: legacy C3_NP/format-v1 bitstream/benchmark expectations and an empty factorial-comparison expectation. They are not regressions introduced by the current host-retune/control-plane integration.

## Resolved today
- Temporary SSH banner timeout was caused by the Windows VPN path. Disabling the VPN restored `linux.ferdowsi.cloud:2220` immediately.
- Old 48CPU/44-worker active configuration references were removed from executable/test/control paths for the current 8c/16G/100G server.
- Public scientific self-hosted control workflow conflict was resolved in favor of the approved private-control-repo design.
- Seven-method engineering dry-run and manuscript-workflow gaps were implemented and tested.

## Latest gate results
- Worker performance gate passed with selected_workers=4 and fresh-cache confirmation.
- Seven-method two-pair engineering dry run passed: 14/14 embeddings, 308/308 evaluations, zero operational failures.
- Active blocker: publish implementation, create/validate/publish baseline freeze v2, then regenerate exact-SHA finalization/preflight.
