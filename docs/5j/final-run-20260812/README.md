# FINAL-5J verified result snapshot (2026-08-12)

This directory is the reviewable GitHub reporting package for the completed FINAL-5J-v1 run. It contains analysis outputs, raw evaluation rows, final tables/figures, run/finalization metadata, engineering dry-run evidence, worker-selection evidence, and key runtime/stability evidence. The large production cache is deliberately retained outside Git.

## Source lineage

- Scientific production source commit: `2891c2a1ad1ce725038ed0a7524adf6c23abcfa0`
  - tree: `8e50380493ae6217638246b8047afd0b7ec84c53`
  - commit subject: `fix: preserve internal clean scientific failures`
- Final analysis source commit: `45ce51220d14ab10d480c734fe0a22b5a860c4bc`
  - tree: `6f1281f2124cc41d044d998d3eadab3a3ddd1705`
  - parent: the production source commit above
  - commit subject: `analysis: normalize mixed scalar parquet fields`

The post-production analysis commit changes analysis serialization/error handling only; the production scientific execution remains attributable to `2891c2a...`.

## Frozen protocol and run identity

- Protocol: `FINAL-5J-v1`
- Plan ID: `ec0be4f6b76c8a63399be3385ae18f2e3931290becb8fe80c58845025cbb5e30`
- Run ID: `5j-ec0be4f6b76c8a63399b`
- Total tasks: `8950`
- Embeddings: `530` = 350 main + 90 payload sweep + 90 PSNR sweep
- Evaluations: `8420` = 7700 main + 360 payload sweep + 360 PSNR sweep
- Dispatcher completion status: `run_complete_local`
- Production workers: `20`
- Embedding operational failures: `0`
- Evaluation operational failures: `0`

## Final analysis inventory

- Raw evaluation rows: `8420`
- Missing rows: `0`
- Invalid rows: `0`
- Partial analysis: `false`
- Bootstrap repetitions: `10000`
- `analysis/analysis.json` SHA256: `7e925316998cc6cdc6e5863c45a3567b3a8271b79e35c9f595d2c3d6ed13785c`
- `analysis/raw_evaluations.parquet` SHA256: `2987eb95303bdb1f8438af26b696d617a35a2c59e80dad2881ae85c7360e793f`

## Directory map

- `analysis/`: complete analysis-v2 outputs and raw evaluation rows.
- `tables/`, `figures/`: final generated reporting artifacts.
- `run/`: key final production run metadata (summary, preflight, state, plan, dispatcher summary).
- `finalization/`: frozen plan/runtime binding and input-readiness evidence.
- `dry-run/`: engineering dry-run summary, state, and execution plan.
- `worker-benchmark/`: worker selection/confirmation evidence and launcher logs, excluding verbose per-task event streams.
- `runtime-config/`: production service/runtime identity configuration.
- `runtime-evidence/`: key Stage-0, stability, and transform-audit evidence.
- `SHA256SUMS.txt`: SHA256 inventory for this reporting package (excluding the checksum file itself).
- `COLD_BACKUP.txt`: operator-side location/hash of the large production cache, which is not tracked in GitHub.

## Deliberately excluded from GitHub

The 1.37 GiB production cache, OAuth/rclone configuration, SSH credentials, restricted source image/object bytes, native-Windows checkout, and verbose engineering caches/event streams are not part of this branch. The production cache is preserved separately on Windows with its recorded SHA256.

This snapshot is intended to be the immutable results base for the manuscript-development branch `paper/final-5j`.
