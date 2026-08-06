# Dedicated FINAL-5J-v1 Runner Boundary

This document defines the simplified runner after the author correction that backup occurs only after the full project is complete.

## 1. Separation rule

The historical 64/88-row runtime and evidence remain immutable. The 5J runner may reuse its generic content store, checkpoint, resume, monitoring, and atomic-write primitives, but it must use a separate 5J plan and namespace.

## 2. Authoritative input

The runner consumes one frozen expanded execution plan. It must not create tasks from observed results, directory contents, or ad-hoc CLI expansion.

Before execution it verifies:

- plan schema and exact counts;
- source, config, seed, manifest, and baseline fingerprints;
- input SHA-256 values;
- transform/runtime/stability readiness;
- `science_ready=true`.

A remote backup backend is not a preflight requirement for numerical scheduling.

## 3. Task states

```text
planned
running
locally_complete
scientific_failure
operational_failure
blocked_by_local_dependency
```

A scientific failure is a valid completed observation and is stored locally like every other result. An operational failure remains a failed attempt and may be retried under a bounded policy.

## 4. Embedding tasks

For each method:

1. verify cover and secret bytes;
2. load the task config;
3. encode and embed the declared payload;
4. run local acceptance checks;
5. atomically write artifacts and metrics;
6. validate local schema and hashes;
7. mark the object `locally_complete`.

No upload occurs and no remote acknowledgement is required.

## 5. Evaluation tasks

An evaluation may start as soon as its embedding object is locally valid. It:

1. verifies the local embedding and stego hashes;
2. applies the frozen channel and seed;
3. extracts and decodes;
4. records recovery, failure severity, metrics, runtime, and provenance;
5. atomically validates the local object;
6. marks it `locally_complete`.

## 6. Cache and resume

Cache reuse requires only local object-ID, schema, and SHA-256 validation. Incomplete directories are quarantined. Restart reconstructs progress from the local content store and does not depend on a backup ledger.

## 7. Parallel execution

The runner starts with 16 single-threaded workers on the 32-CPU/64-GiB server. Worker count is adjusted only after a short engineering benchmark shows actual CPU, RAM, swap, I/O, failure, and throughput behavior.

## 8. Final backup

After all 530 embeddings, 8,420 evaluations, analyses, tables, figures, manuscript outputs, logs, and inventories are locally complete:

1. build the final archive packages;
2. generate checksums and the final ledger;
3. upload once to the approved remote destination;
4. verify the uploaded archive;
5. permit server evacuation.

Final backup is outside the scheduling loop.

## 9. First acceptance target

Before the main run, use two engineering-only pairs to verify:

- all seven method paths once B1/B2 are implemented;
- local atomic object creation;
- local resume after one forced process termination;
- output schemas and analysis inputs;
- worker stability at the selected concurrency.

The dry-run objects are engineering evidence only and never enter the final 50-pair result set.
