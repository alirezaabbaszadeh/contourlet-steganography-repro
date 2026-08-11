# FINAL-5J 8c/16G/100G checkpoint — 2026-08-11

Status: **implementation fixes validated locally; server benchmark blocked by SSH banner timeout**

## Reference state

- Scientific/control branch before today's tuning changes: `agent/server-control-plane`
- GitHub parent commit: `53e8530a76c55936a3e350555ec1df4a8ca536ee`
- Tested local commit preserved in WSL: `cd327b31aaf1b8be840abec7934c9ab2f4e160cb`
- Local checkout: `/opt/sentinelx-cloud-core/ctsteg-8core-tuning`
- Scientific FINAL-5J execution has **not** started: `0 / 530` embeddings and `0 / 8420` evaluations.

## Target host profile

The implementation has been retuned for the current Ferdowsi server class:

- 8 logical CPU cores;
- 16 GB advertised RAM, with a minimum 14 GiB visible-memory gate;
- 100 GB advertised storage, with a minimum 90 GiB visible root-capacity gate;
- at least 30 GiB free storage required during worker tuning;
- zero tolerated swap I/O during measured trials.

Profile ID: `ferdowsi-8c16g-100gb-v2`.

## Worker policy implemented

The deterministic engineering tuning ladder is now:

```text
4 stable + sufficient headroom -> test 6
4 unsafe -> test 2
2 unsafe -> test 1
2 or 1 stable after fallback -> accept fallback
6 stable + >=7.5% gain over 4 + sufficient headroom -> test 7
6 stable but <7.5% gain over 4 -> accept 4
7 stable + >=5% gain over 6 -> accept 7
7 stable but <5% gain over 6 -> accept 6
6 or 7 unsafe -> stop scale-up and retain the best stable lower candidate
```

Hard cap is **7 workers**. One logical CPU is always reserved for OS/monitoring/Octave coordination/I/O. Numerical workers remain single-threaded internally.

Main dispatcher defaults are now:

- `workers=4`
- `reserve_cpus=1`
- `reserve_memory_gib=3.5`
- `worker_memory_gib=1.5`
- `hard_cap=7`

The runtime worker resolver may reduce concurrency when current RAM is insufficient; it may never exceed 7.

## Safety gates

A measured worker candidate is unsafe after any of:

- operational task failure;
- OOM event;
- nonzero swap I/O;
- available RAM below 3 GiB;
- free storage below 30 GiB;
- p95/sustained I/O wait above the frozen rejection threshold;
- cache/object validation failure;
- runtime/toolbox binding change.

The provisional winner must still be repeated once with a fresh benchmark cache before scientific execution.

## Implementation touched

The local tested commit updates the worker tuning config/logic, worker trial host/storage gates, dispatcher resource defaults, server-control worker cap, private runner documentation/labels, workflow expectations, and associated tests. The local commit contains 23 changed files with 431 insertions and 399 deletions.

## Validation evidence

All targeted suites pass on the local commit:

- worker tuning: **12 / 12 passed**;
- server control-plane: **36 / 36 passed**;
- worker trial: **5 / 5 passed**;
- FINAL-5J dispatcher: **3 / 3 passed**;
- total targeted validation: **56 tests passed**;
- `python -m py_compile`: passed for the changed Python execution/control modules;
- `python -m json.tool configs/5j/worker_autotune_v1.json`: passed;
- `git diff --check`: passed;
- audit found no active references to the superseded 6-worker cap / old 48-vCPU runner label in the execution paths covered by this change.

## Server connectivity blocker

At the end of this session, direct SSH to `linux.ferdowsi.cloud` could not reach the SSH banner. Both historical ports were tested from the established WSL control host:

- TCP/2220: `Connection timed out during banner exchange`;
- TCP/2284: same banner-stage timeout during the earlier probe.

Because the connection did not reach authentication, this is not a PEM/key-permission failure. No worker benchmark was started and no server-side scientific artifact was modified during this blocked interval.

## Shutdown state

A controlled `sudo poweroff` could **not** be issued because SSH was unavailable. Server power state therefore must be checked in the Ferdowsi provider panel before considering the machine safely stopped. Do not assume an SSH banner timeout means the VM is powered off.

## Exact continuation order

When resuming:

1. Power on / confirm the intended 8-core, 16-GB, 100-GB VM in the Ferdowsi panel.
2. Restore SSH on port 2220 and verify `hostname`, `nproc`, `MemTotal`, root disk size/free space, Python, Git, and Octave/PDFB paths.
3. Publish/sync the tested local commit `cd327b31aaf1b8be840abec7934c9ab2f4e160cb` onto the reviewed GitHub branch before numerical use.
4. Run bounded `health_check`, bootstrap/runtime gates, and verify the exact scientific commit.
5. Run engineering worker trial at 4 workers with a fresh cache.
6. Follow only the frozen decision output: test 6 if allowed; test 7 only if 6 passes all gates and gains >=7.5% over 4.
7. Confirm the selected winner once with a fresh cache and require <=10% throughput variation.
8. Run the separate two-pair, seven-method engineering dry-run (`C0/C1/C2/C3_NP/C3/B1/B2`) in its non-scientific namespace.
9. Only after all gates pass may FINAL-5J scientific execution be considered.

No historical scientific result is to be overwritten or used as a substitute for these gates.