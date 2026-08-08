# Durable parallel execution gate

## Status and boundary

The durable runtime is implemented for the lean `DIGITAL_A_D` plan:

- 16 content-addressed embedding and clean-decode checkpoints;
- 48 mandatory attacked-channel checkpoints;
- 0 to 24 automatically triggered hard-channel checkpoints;
- 64 mandatory evaluation rows and an absolute cap of 88;
- bounded process parallelism with nested BLAS/OpenMP threads disabled;
- atomic object publication, deep checksum validation, resume, and export.

This infrastructure does not approve a transform. Haar and the directional
proxy remain engineering controls. The final scientific run remains blocked
until a real PDFB adapter, Stage-0 evidence, and human review exist.

## Why the cache is the source of truth

`state.json` is a readable progress view, not the authoritative checkpoint.
Each completed task is first published as an immutable cache object containing:

```text
COMPLETED.json
_inventory.json
task.json
resource.json
stdout.log
stderr.log
scientific payload files
```

Every inventory entry stores its size and SHA-256. A cache hit requires a deep
validation of the marker, inventory hash, file sizes, and file hashes. If the
server dies after object publication but before `state.json` is updated, the
next invocation discovers the object and skips it.

An interrupted task remains under `cache/attempts/`. It is not mistaken for a
complete result. Invalid published objects are moved to `cache/quarantine/`
with their reason preserved before the same deterministic task is retried.

## Object identity

Embedding identity includes:

- protocol and object-schema versions;
- numerical source fingerprint;
- config and stability hashes;
- transform fingerprint;
- decoded cover and secret hashes;
- pair and method.

Channel-evaluation identity additionally includes:

- embedding object identity;
- exact channel condition;
- the deterministic pair-channel realization identifier.

The numerical fingerprint excludes orchestration-only files. Fixing a queue,
report, or systemd wrapper therefore does not invalidate valid numerical
objects. A numerical source change, config change, input-byte change,
stability change, transform change, or object-schema change produces new
addresses.

The Git commit and dirty state are still retained as provenance. Content bytes,
not a documentation-only commit change, determine whether scientific work must
repeat.

## Task graph and resume granularity

The checkpoint boundary is deliberately coarse enough to be auditable and
fine enough to avoid expensive repetition:

1. one `embed + clean extract + evidence` object per pair-method;
2. one `attack + extract + metrics + evidence` object per channel evaluation;
3. aggregation and packaging, which can be regenerated from cached objects.

If power is lost inside one embedding, only that embedding is retried. If it is
lost inside one attacked evaluation, the embedding and every other completed
evaluation are reused. The failed attempt remains in the audit trail.

## Mandatory interruption gate

Install the research and test extras:

```bash
python -m pip install -e '.[research,test]'
```

Run the gate on the target Ubuntu server and persistent disk:

```bash
ctsteg runtime-gate \
  --output-dir /srv/ctsteg/gates \
  --workers 2 \
  --jobs 8
```

The gate starts a real process pool, waits for committed objects, sends
`SIGKILL` to the complete process group, restarts the identical run, and
checks:

- pre-interruption objects remain byte-identical;
- the restart reports those objects as cache hits;
- the stale lock is preserved;
- all jobs finish;
- every cache object passes deep validation;
- a self-contained archive is created;
- every archived file listed in `checksums.sha256` verifies.

The current runtime-code fingerprint is embedded in
`latest_runtime_gate.json`. Any runtime implementation change invalidates an
old gate report. `digital-research-run` refuses to start without a currently
valid report.

## Strict plan preflight

The core manifest must contain exactly four unique `traceability_core` rows,
without a seed value. These metadata columns are mandatory and verified:

```text
cover_source_id
secret_source_id
cover_rights
secret_rights
cover_sha256
secret_sha256
cover_array_sha256
secret_array_sha256
```

Decoded cover and secret arrays must also be unique across the four rows.

Generate a plan without executing:

```bash
ctsteg digital-research-plan \
  --manifest /srv/ctsteg/inputs/traceability-core-v2.csv \
  --config configs/digital_ad/final_locked_v1.toml \
  --stability-profile /srv/ctsteg/inputs/stability-v2.json \
  --output /srv/ctsteg/locks/research-plan.json \
  --engineering-control
```

`--engineering-control` is required for the current Haar/proxy adapters and
labels all output accordingly. It is not permitted as final PDFB evidence.

The planner rejects any shape other than:

```text
16 embeddings
64 mandatory rows
24 maximum conditional rows
88 absolute maximum rows
```

## Execute or resume

```bash
ctsteg digital-research-run \
  --manifest /srv/ctsteg/inputs/traceability-core-v2.csv \
  --config configs/digital_ad/final_locked_v1.toml \
  --stability-profile /srv/ctsteg/inputs/stability-v2.json \
  --runtime-gate-report /srv/ctsteg/gates/latest_runtime_gate.json \
  --output-root /srv/ctsteg/results \
  --cache-dir /srv/ctsteg/cache \
  --workers 0 \
  --minimum-free-disk-gib 100 \
  --require-parquet \
  --engineering-control
```

Running the same command again is the resume operation. There is no separate
unsafe overwrite mode.

Live resource saturation, checkpoint throughput, and ETA are exposed without
writing inside the research run:

```bash
ctsteg research-status \
  --output-root /srv/ctsteg/results \
  --watch
```

The monitor reports algorithm CPU relative to allocated worker capacity,
whole-host CPU and I/O wait, RAM pressure, process-tree I/O, mandatory and
conditional progress, tasks/hour, and a throughput-based ETA. See
[`SERVER_DEPLOYMENT.md`](SERVER_DEPLOYMENT.md) for the complete Ubuntu,
MATLAB, systemd, and monitoring contract.

`--workers 0` chooses the minimum of:

- available CPUs minus the reserved CPUs;
- available RAM minus the reserved RAM, divided by estimated RAM per worker;
- job count;
- the hard worker cap, 16 by default.

The defaults match the recommended 32-vCPU/64-GiB server:

```text
reserve CPUs: 4
reserve RAM: 12 GiB
estimated RAM per worker: 3 GiB
hard cap: 16 workers
```

Set an explicit worker value only after measuring the recorded
`worker_peak_rss_mb`. An unsafe request is rejected instead of silently
oversubscribing the host.

The runner records total/used/free bytes for both the result and cache
filesystems. It rejects the run before any worker starts when either location
does not meet `--minimum-free-disk-gib` (the service default is 100 GiB).

## Channel realization and hard checks

One realization is derived from:

```text
SHA256(protocol_version || pair_id || channel_id)
```

The method identifier is deliberately absent, so C0-C3 receive the same
stochastic realization for a pair and channel.

After all 64 core rows exist, each family is evaluated independently. A hard
check is scheduled only when:

- all clean rows pass; and
- the complete C0/C3 medium evidence exists; and
- both methods are strictly saturated at EUR 0 or EUR 1, or C0-C3 EUR is at
  least 0.01 for at least three of four pairs.

Only C0/C3 are scheduled at the hard point. Each family can add exactly eight
rows. The runner writes a decision for all three families, including
`not_triggered` and blocked decisions.

## Result and cache layout

```text
OUTPUT_ROOT/
  cache/
    objects/<sha-prefix>/<sha-rest>/
    attempts/<sha-prefix>/<sha-rest>/<attempt-id>/
    quarantine/<sha>-<time>-<id>/
  runs/<run-id>/
    plan.json
    runtime_gate.json
    resource_plan.json
    state.json
    events/
    trigger_decisions.json
    reports/
      evaluations.csv
      evaluations.json
      evaluations.jsonl
      evaluations.parquet
      summary.csv
      summary.json
    checksums.sha256
    run_summary.json
    exports/
      experiment-<run-id>-<bundle-id>.tar.gz
      experiment-<run-id>-<bundle-id>.tar.gz.json
```

Each embedding object retains the original and decoded inputs, stego,
difference, recovered image when valid, bitstream and coefficient manifests,
capacity, transform audit, lambda, metrics, failures, runtime, environment,
Git state, and logs.

Each channel object retains the attacked image, recovered image when valid,
packed extracted bits and their hash, decode/CRC/EUR/BER metrics, failures,
runtime, memory, environment, hashes, and logs.

The bundle includes all referenced immutable objects and failed/incomplete
attempts. The archive is created through a temporary file, verified against
every entry in `checksums.sha256`, and only then atomically renamed. The same
full verification is required before reuse. A resume with an unchanged object
set reuses the existing archive instead of creating a duplicate.

## Exit codes

| Code | Meaning | systemd behavior |
|---:|---|---|
| `0` | complete | stop successfully |
| `2` | scientific clean gate blocked | do not loop |
| `3` | operational stage failure | restart and resume |
| `64` | service environment invalid | do not loop |

## systemd

Install:

```bash
sudo useradd --system --home /nonexistent --shell /usr/sbin/nologin ctsteg
sudo install -d -o ctsteg -g ctsteg -m 0750 /srv/ctsteg
sudo install -d -o root -g ctsteg -m 0750 /etc/ctsteg-research
sudo install -m 0755 scripts/run_research_service.sh \
  /opt/ctsteg/current/scripts/run_research_service.sh
sudo install -m 0644 deploy/systemd/ctsteg-research@.service \
  /etc/systemd/system/ctsteg-research@.service
sudo install -m 0640 deploy/systemd/research.env.example \
  /etc/ctsteg-research/final.env
sudo systemctl daemon-reload
sudo systemctl enable --now ctsteg-research@final.service
```

Edit the environment file first. The supplied unit writes only under
`/srv/ctsteg`, restarts operational failures, preserves all cache state on a
persistent disk, and starts again after reboot.
