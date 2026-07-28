# Lean development plan

## Objective

Reach one bounded, publishable research execution without building an
unnecessary experiment platform. The plan ends at 64 mandatory result rows and
at most 24 conditional rows.

## Non-negotiable constraints

- P0 remains numerically frozen.
- The real PDFB/Contourlet gate must pass before scientific execution.
- Every method embeds exactly 222,360 protected bits.
- Stego PSNR remains `45.0 ± 0.1 dB`.
- C0-C3 are retained only where needed to separate A, D, and A-by-D.
- There is one deterministic channel realization per pair and attack.
- No seed sweep, power-based pair expansion, or full nine-level attack grid.
- Mandatory run budget: 64 rows.
- Absolute run budget: 88 rows.

## Work packages

### WP0 - merge and freeze

Deliverables:

- merge the PDFB gate branch;
- merge the documentation branch;
- verify all tests;
- verify all six protected P0 files;
- record the exact research commit.

Acceptance:

- CI is green;
- P0 hashes match;
- the worktree used for research is clean.

### WP1 - real PDFB evidence

Deliverables:

- run MATLAB with the approved Contourlet Toolbox;
- archive raw Stage-0 evidence;
- run the independent Python validator;
- complete human review of paths, hashes, band shapes, capacity,
  reconstruction, and coefficient probes.

Acceptance:

- the exact profile is accepted for implementation;
- eligible capacity is at least 222,360;
- no proxy is promoted to PDFB evidence.

Stop if this package fails.

### WP2 - PDFB adapter

Deliverables:

- versioned forward and inverse adapter;
- transform fingerprint enforcement;
- selected-band read/write interface;
- clean reconstruction tests;
- clean C0 smoke on one calibration pair.

Acceptance:

- adapter output matches the reviewed Stage-0 structure;
- clean reconstruction and coefficient writability pass;
- no P0 file changes.

### WP3 - four-pair data lock

Deliverables:

- source inventory for Baboon, Boat, Peppers, and House;
- four fixed 128x128 secrets;
- four-row traceability manifest;
- at most two calibration pairs;
- hash, preprocessing, rights, and duplicate preflight.

Acceptance:

- exactly four unique research pairs;
- no repeated row for random seeds;
- calibration and research inputs are disjoint;
- the run planner returns 64 mandatory and at most 88 total rows.

### WP4 - lean execution profiles

Deliverables:

- `core` profile: Clean, JPEG 70, Gaussian 10, S&P 0.03;
- three independent optional hard profiles: JPEG 50, Gaussian 15, S&P 0.05;
- deterministic realization derivation shared across methods;
- run-budget validator;
- trigger recorder.

Acceptance:

- low-severity points are not scheduled;
- core profile contains exactly 64 rows;
- each hard family contains exactly 8 rows and only C0/C3;
- more than 88 total rows fails closed.

### WP5 - core execution

Deliverables:

- 16 saved stego artifacts;
- 16 clean rows;
- 48 representative attacked rows;
- complete failure and provenance fields.

Acceptance:

- 64 rows exist exactly once;
- no method/pair/channel cell is silently dropped;
- operational reruns reuse the same deterministic realization and retain the
  failed attempt;
- algorithmic failures remain outcomes.

### WP6 - conditional confirmation

For each family, evaluate the frozen trigger:

- medium severity is saturated; or
- C3 improves EUR by at least 0.01 in at least three of four cases and a hard
  confirmation is needed.

Deliverables:

- trigger status for all three families;
- zero or eight rows per triggered family;
- at most 24 added rows.

Acceptance:

- no untriggered family is run;
- C1/C2 are not repeated at hard severity;
- total rows never exceed 88.

### WP7 - analysis and manuscript evidence

Deliverables:

- raw long-form table;
- per-case A, D, A-by-D, and C0-C3 contrasts;
- mean, median, range, and direction count;
- automatically generated tables and figures;
- updated claim matrix;
- manuscript text bounded to the four traceability cases.

Acceptance:

- no population-generalization claim;
- no bootstrap, sign-flip, Wilcoxon, Holm, or achieved-power analysis;
- positive, neutral, mixed, and negative results are all reportable;
- every reported number traces to a raw row.

## Dependency order

```text
WP0 -> WP1 -> WP2 -> WP3 -> WP4 -> WP5 -> WP6 -> WP7
```

WP6 may add zero rows. It is a decision package, not an obligation to run more
experiments.

## Cost controls

| Control | Enforced limit |
|---|---:|
| Research pairs | 4 |
| Calibration pairs | at most 2 |
| Core embeddings | 16 |
| Mandatory result rows | 64 |
| Conditional rows per family | 8 |
| Conditional total | at most 24 |
| Overall result-row cap | 88 |
| Scientific seed repetitions | 0 |

The implementation must compute the plan before execution and fail closed when
any limit is exceeded.

## Risks and responses

| Risk | Response |
|---|---|
| PDFB fails | stop and report; do not create another proxy |
| capacity below 222,360 | stop; do not lower payload |
| clean decode fails | classify defect versus algorithmic failure; do not expand |
| medium attack is uninformative | run only that family's predefined hard point |
| C3 is neutral or worse | report and stop; do not add runs |
| four cases are too narrow for a universal claim | keep the claim case-bounded |
| a future reviewer requests generalization | propose a separate budgeted study |

## Definition of done

The development phase is complete when:

1. the reviewed PDFB adapter exists;
2. the four-pair manifest is frozen;
3. the 64-row core executes once;
4. conditional triggers add no more than 24 rows;
5. results and failures are immutable and traceable;
6. the manuscript makes no claim stronger than this bounded evidence.
