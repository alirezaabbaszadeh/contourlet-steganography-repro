# FINAL-5J-v1 worker autotuning protocol

Status: implementation baseline  
Target host class: 32 logical CPUs, 64 GiB RAM  
Protocol: `FINAL-5J-v1`

## Purpose

Choose the fastest stable worker count from measured end-to-end throughput. The objective is not to display 100% CPU usage; it is to maximize completed, hash-verified tasks per hour without swap, OOM, cache corruption, excessive I/O wait, or loss of operating headroom.

Worker tuning is operational calibration. It must not change images, payloads, methods, attacks, seeds, numerical parameters, or scientific task identities.

## Mandatory order

The first measured trial is always 16 workers. Subsequent trials are selected only by the frozen decision rules below.

Candidate ladder:

- downward: 12, then 8;
- upward: 20, then 24, then 28;
- 32 workers are forbidden on the 64-GiB host because four CPUs and operating-memory headroom remain reserved.

Every numerical worker remains single-threaded for OpenMP, OpenBLAS, MKL, NumExpr, VecLib, and BLIS. Parallelism is across independent process workers.

## Representative workload

The tuning set must be frozen before timing and must be excluded from outcome-driven scientific decisions. It should use the real PDFB runtime and format-v2 code path and contain enough independent work to keep 16 workers busy:

- at least 32 internal embedding tasks;
- at least 128 dependent evaluation tasks;
- all five internal methods represented;
- at least two payload fractions;
- clean plus JPEG, Gaussian, and salt-and-pepper evaluations;
- no B1/B2 tasks until their adapters are approved.

A trial with cache hits is invalid for throughput comparison. Warm-up tasks use a separate cache namespace and are not timed.

## Measurements

Each trial records:

- worker count and task selection hash;
- wall-clock duration;
- completed and failed task counts;
- tasks per hour for embeddings, evaluations, and combined workload;
- CPU busy percentage and I/O-wait percentage over time;
- minimum available memory;
- maximum swap usage and swap-in/swap-out activity;
- per-object peak RSS, including median, p95, and maximum;
- load average;
- disk free-space floor and storage errors;
- backup/upload throughput separately from compute throughput;
- OOM-kill and operational-failure evidence.

Scientific failures are valid completed evaluations. Operational failures are trial failures.

## Immediate rejection conditions

A worker count is unsafe if any of the following occurs:

- any OOM kill or memory-allocation failure;
- any nonzero swap-in/swap-out activity during the measured interval;
- available memory falls below 8 GiB;
- an operational task failure occurs;
- cache validation or object commit fails;
- sustained I/O wait exceeds 15%;
- the runtime or toolbox binding changes between trials.

An unsafe 16-worker trial is followed by 12 workers. An unsafe 12-worker trial is followed by 8 workers. No upward trial is allowed after an unresolved unsafe result.

## Scale-up rules

After a stable 16-worker trial, 20 workers may be tested only when all conditions hold:

- p95 worker RSS leaves at least 10 GiB projected host headroom at 20 workers;
- no swap activity occurred;
- p95 I/O wait is at most 10%;
- mean CPU busy is at least 70%;
- there are no operational failures.

After a stable 20-worker trial, 24 workers may be tested only if the combined tasks/hour improves by at least 7.5% over 16 workers and projected memory headroom remains at least 10 GiB.

After a stable 24-worker trial, 28 workers may be tested only if throughput improves by at least 7.5% over 20 workers and projected memory headroom remains at least 10 GiB.

## Stop and selection rules

Stop increasing when any of these occurs:

- throughput gain over the previous stable candidate is below 5%;
- I/O wait rises above 10%;
- projected memory headroom falls below 10 GiB;
- CPU busy does not improve while load or latency rises;
- backup bandwidth becomes the stage bottleneck;
- any rejection condition occurs.

The selected worker count is the stable candidate with the highest measured combined tasks/hour. A higher worker count is not selected merely because it uses more CPU.

## Repetition and acceptance

The provisional winner is rerun once with a fresh benchmark cache. It is accepted only when:

- both runs are stable;
- throughput differs by no more than 10%;
- task outputs remain bit/hash identical;
- no scientific identity changes;
- remote backup verification succeeds for the retained trial report and any retained objects.

The accepted count, host fingerprint, trial hashes, and decision report are committed to the run capsule before the five-pair pilot.

## Hardware-change rule

All tuning must occur after the 32-CPU/64-GiB upgrade and before final runtime-binding approval. Changing CPU/RAM after acceptance requires repeating this protocol. The scientific run must not silently mix worker-tuning regimes or host fingerprints.
