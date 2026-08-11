# FINAL-5J-v1 worker autotuning protocol

Status: **locked before performance results**
Protocol: `FINAL-5J-v1`
Target profile: `ferdowsi-8c16g-100gb-v2`

## Target host

The numerical host is frozen as:

- 8 logical CPUs;
- 16 GB advertised RAM (at least 14 GiB visible to Linux);
- 100 GB advertised storage (at least 90 GiB visible root capacity);
- one logical CPU always reserved for the operating system, monitoring, Octave coordination, and I/O;
- zero tolerated swap I/O during measured trials;
- at least 30 GiB free storage during worker tuning.

Changing CPU, RAM, or storage class after worker acceptance requires repeating this protocol.

## Purpose

Choose the fastest stable process count from measured end-to-end throughput without changing any scientific task identity, image, payload, method, attack, seed, or numerical parameter. Every numerical worker is single-threaded internally; parallelism is only across independent processes.

## Frozen candidate order

The first measured trial is always **4 workers**. The only allowed transitions are:

```text
4 stable + sufficient headroom -> test 6
4 unsafe -> test 2
2 unsafe -> test 1
2 or 1 stable after fallback -> accept fallback
6 stable + >=7.5% gain over 4 + sufficient headroom -> test 7
6 stable but <7.5% faster than 4 -> accept 4
7 stable + >=5% gain over 6 -> accept 7
7 stable but <5% faster than 6 -> accept 6
6 or 7 unsafe -> stop scaling and retain the best stable lower candidate
```

No worker count above **7** is permitted on this host profile.

## Representative workload

The benchmark remains engineering evidence only and uses a fresh cache. It must contain at least:

- 32 internal embedding tasks;
- 128 dependent evaluations;
- all five internal methods `C0/C1/C2/C3_NP/C3`;
- at least two payload fractions;
- clean, JPEG, Gaussian, and salt-and-pepper channel families.

B1/B2 are excluded from worker-count tuning; the later seven-method engineering dry run is a separate gate.

## Measurements

Each trial records worker count, task-selection hash, wall time, completed/failed task counts, combined tasks/hour, CPU busy, p95 I/O wait, minimum available RAM, p95/max worker RSS, swap I/O, OOM evidence, load average, and minimum free storage.

## Immediate rejection conditions

A candidate is unsafe if any of the following occurs:

- any operational task failure;
- any OOM event;
- any nonzero swap-in/swap-out activity;
- available memory falls below 3 GiB;
- free storage falls below 30 GiB;
- sustained/p95 I/O wait exceeds the locked rejection threshold of 15%;
- cache validation or immutable-object commit fails;
- runtime/toolbox binding changes between trials.

Scientific failures remain valid scientific observations and do not by themselves invalidate a worker trial.

## Scale-up gates

A stable 4-worker trial may test 6 only when:

- mean CPU busy is at least 70%;
- p95 I/O wait is at most 10%;
- projected memory headroom at 6 workers remains at least 3.5 GiB, using measured p95 worker RSS with a 20% safety factor;
- no rejection condition occurred.

Six workers must improve combined throughput by at least 7.5% over four workers before seven workers can even be attempted.

A stable 6-worker trial may test 7 only when the same CPU, RAM, swap, storage, and I/O gates still pass. Seven workers are accepted only if combined throughput improves by at least 5% over six workers. Otherwise six workers remain selected. One logical CPU remains reserved at all times.

## Main dispatcher defaults

The scientific dispatcher defaults to:

- `workers=4`;
- `reserve_cpus=1`;
- `reserve_memory_gib=3.5`;
- `worker_memory_gib=1.5`;
- `hard_cap=7`.

The runtime worker resolver may lower the effective safe bound when currently available memory is insufficient. It must never raise the count above seven.

## Repetition and acceptance

The provisional winner is rerun once with a fresh benchmark cache before scientific execution. Both runs must be stable, task outputs must remain bit/hash identical, and throughput variation must stay within 10%.

The accepted worker count and benchmark evidence are operational configuration only; they do not change the frozen `530 / 8420` scientific task matrix.
