# DIGITAL_A_D stage-gate status

## Implemented

### Stage 0 — Transform audit

- machine-readable audit command;
- all band shapes and counts;
- candidate capacity and utilization;
- reconstruction error and redundancy;
- transform fingerprint;
- explicit proxy/control/PDFB claim boundary.

### Stage 1 — Digital transport

- Base/Detail split and lossless recombination;
- MSB-first bit and byte packing;
- self-contained RS(255,127) and RS(255,191);
- fixed header, CRC32, canonical seed derivation;
- scrambling, interleaving, exact 222,360-bit payload;
- explicit decoding failures and no fabricated output.

### Stage 2 — C0 clean control

- exact coefficient slot map;
- uniform capacity and fixed power;
- coefficient-domain zero-BER test;
- inverse/rounding/uint8 boundary;
- PSNR-constrained lambda search;
- full artifact package.

The orthogonal control clean path passes. The existing directional proxy clean
path is an expected recorded failure and is not relabelled as a successful
Contourlet experiment.

### Stage 3 — C0/C1/C2/C3 pilot

- all four methods;
- adaptive A and unequal D;
- deterministic JPEG Q=70 and Gaussian variance=10 pilot;
- comparative long-form rows;
- no rotation/crop in the digital path.

### Stage 4 — Calibration

- calibration-only manifest guard;
- fixed attack-based stability estimation;
- transform-bound stability artifact.

### Stage 5 — Locked benchmark

- multi-method manifest runner;
- input hashes, seed/split, artifacts, failures, raw rows and summaries;
- final nine-condition digital attack suite.

The code path is implemented. A paper-final dataset has deliberately not been
invented or executed; its license, manifest, split, and hashes must be frozen
before a scientific run.

### Stage 6 — Statistical evidence

- pair-level seed aggregation;
- paired bootstrap interval;
- sign-flip test;
- rank-biserial effect;
- Holm correction;
- A and D main effects and A×D interaction.

### Stage 7 — Reproducibility package

- generated JSON/CSV evidence;
- images, capacity, bitstream, permutation and coefficient-map artifacts;
- Git/environment provenance and timing;
- P0 freeze guard and CI smoke route.

## Remaining claim gate

Software completion does not remove the paper's missing PDFB parameters.
Direct superiority over the article remains conditional on one of:

1. author code and exact parameters;
2. an approved and documented MATLAB PDFB interpretation;
3. a manuscript claim explicitly limited to the controlled digital factorial
   experiment.
