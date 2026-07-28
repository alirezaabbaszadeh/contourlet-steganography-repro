# DIGITAL_A_D stage-gate status

## Implemented

### Stage 0 - transform audit

- machine-readable audit;
- band shapes and counts;
- capacity and utilization;
- reconstruction and redundancy;
- transform fingerprint;
- explicit proxy/control/PDFB claim boundary;
- MATLAB audit bridge and fail-closed Python validator.

Real MATLAB evidence and human review are still pending.

### Stage 1 - digital transport

- Base/Detail split;
- RS, CRC, fixed header, scrambling, and interleaving;
- exact 222,360-bit payload;
- deterministic implementation metadata;
- explicit failures with no fabricated output.

### Stage 2 - method controls

- C0-C3;
- adaptive A and unequal D;
- exact slot maps;
- PSNR-constrained lambda search;
- Haar engineering control;
- recorded failure of the redundant directional proxy.

### Stage 3 - calibration and benchmark infrastructure

- calibration-only manifest guard;
- transform-bound stability artifact;
- multi-method runner;
- hashes, provenance, artifacts, failures, and raw rows;
- per-condition A, D, and A-by-D analysis.

The runner can support broader profiles, but the final research schedule is now
the lean v2 protocol. Legacy nine-condition and repeated-seed capabilities are
not scheduled.

## Required before the research run

1. execute and review real MATLAB PDFB Stage 0;
2. implement the approved PDFB adapter;
3. lock the four traceability pairs;
4. implement the exact four-condition `core` profile;
5. implement three independent hard profiles;
6. derive one deterministic realization per pair and attack;
7. add a planner that enforces 64 mandatory rows and an 88-row absolute cap;
8. add per-family trigger records;
9. generate descriptive tables and figures from raw rows.

## Lean final gates

| Gate | Pass condition |
|---|---|
| PDFB | raw evidence, independent validation, human approval |
| Capacity | at least 222,360 eligible writable slots |
| Data | exactly four fixed research pairs |
| Core | exactly 16 embeddings and 64 rows |
| Clean | all failures retained and classified |
| Conditional | only triggered C0/C3 families, eight rows each |
| Budget | total no greater than 88 |
| Claims | wording limited to four cases and tested conditions |

Population-level bootstrap, sign-flip, Wilcoxon, Holm, power analysis, and
repeated-seed aggregation are not final-run gates.

## Remaining article-comparison gate

Direct superiority over the source article remains conditional on:

1. author code and complete parameters; or
2. an approved explicit PDFB interpretation plus harmonized transform,
   payload, data, attacks, quantization, and metrics.

Passing the PDFB gate alone does not establish author equivalence.

