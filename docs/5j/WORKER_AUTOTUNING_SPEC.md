# FINAL-5J-v1 worker autotuning protocol

Status: **locked for the 32c64g host before production execution**
Protocol: `FINAL-5J-v1`
Target profile: `ferdowsi-32c64g-100gb-v1`

## Target host

The production host profile is:

- 32 logical CPUs;
- 64 GB advertised RAM, with at least 60 GiB visible to Linux;
- 100 GB advertised storage, with at least 90 GiB root capacity and 30 GiB free during tuning;
- exactly three logical CPUs reserved by an absolute scientific-worker ceiling of 29;
- zero tolerated swap I/O during measured trials.

A fixed CPU-busy percentage is **not** an acceptance or scale-up gate. CPU busy and load are telemetry only. Capacity decisions use measured throughput, marginal throughput per added worker, RAM headroom, OOM/swap evidence, storage headroom, and I/O wait.

## Candidate ladder

The first measured trial is 16 workers. The frozen candidates are:

```text
16
  unsafe -> 12 -> 8 -> 4
  stable -> 20 -> 24 -> 27 -> 29
```

29 is an absolute ceiling; it preserves three logical CPUs for the operating system, runner/control processes, monitoring, and I/O coordination. All scientific workers remain single-threaded internally.

## Engineering workload

Worker tuning is engineering evidence only and uses a fresh cache. Each trial contains 40 embeddings and 160 dependent evaluations (200 tasks total) from the two frozen dry-run pairs, using the five internal methods C0/C1/C2/C3_NP/C3. B1/B2 are excluded from worker-count tuning and are covered by the separate seven-method dry run.

## Immediate rejection

A candidate is unsafe if any of the following occurs:

- any operational task failure;
- any OOM event;
- any nonzero swap I/O;
- available RAM falls below 8 GiB;
- free storage falls below 30 GiB;
- sustained/p95 I/O wait exceeds 15%;
- runtime/toolbox identity changes between trials.

## Scale-up rule

For a safe candidate, scale-up is allowed only when projected memory headroom for the next candidate remains at least 10 GiB and the measured marginal-throughput efficiency ratio is at least 0.30. The ratio compares throughput gained per added worker with baseline throughput per worker from the 16-worker trial. No fixed CPU-utilization percentage participates in this decision.

## Confirmation

The provisional winner must be rerun once with a fresh benchmark cache. Both runs must remain safe and the absolute throughput difference divided by their mean must be at most 10%. The 10% threshold must not be relaxed after observing a result.

If confirmation exceeds 10%, recompute the worker decision from the complete measured history without relaxing the threshold. A lower safe candidate may then become provisional and must itself receive a fresh-cache confirmation before production.

## 2026-08-12 measured outcome

On host `c32` (32 CPUs, 62.79 GiB Linux-visible RAM, no swap):

- 16 workers: 8,927.46 tasks/hour, safe;
- 20 workers: 11,866.56 tasks/hour, safe;
- 24 workers: 12,739.26 tasks/hour, safe;
- 27 workers: 12,101.07 tasks/hour, safe but slower than 24;
- 24 fresh confirmation: 11,118.39 tasks/hour; repeat difference 13.59%, so 24 was rejected as insufficiently repeatable;
- 20 fresh confirmation: 10,941.53 tasks/hour; repeat difference 8.11%, so 20 passed confirmation.

**Selected production worker count: 20.**

These measurements are operational configuration evidence only; they do not alter the frozen 530-embedding / 8,420-evaluation scientific task matrix.
