# Manuscript blueprint for the lean case study

## Working contribution

The manuscript evaluates a controlled digital payload design with:

1. adaptive allocation and power `A`;
2. unequal Base/Detail protection `D`;
3. their joint C3 construction;
4. a fail-closed, explicitly identified PDFB implementation.

The empirical scope is four source-image traceability cases, not an arbitrary
image population.

## Abstract

State:

- the source article and its missing implementation details;
- the separate DIGITAL_A_D contract;
- four methods C0-C3;
- four traceability cases;
- 222,360 protected bits at `45.0 ± 0.1 dB`;
- Clean plus JPEG 70, Gaussian 10, and S&P 0.03;
- whether any predefined hard checks were triggered;
- the actual bounded outcome and limitation.

Do not use universal superiority, exact reproduction, or cryptographic-security
language.

## Introduction

Explain:

- why source-paper traceability and a new digital mechanism are separate;
- why A and D require C0-C3;
- why the study deliberately avoids a large seed and attack matrix;
- that the goal is a cost-efficient mechanism case study.

## Related work

Include:

- transform-domain image steganography;
- contourlet/PDFB variants;
- unequal error protection;
- adaptive coefficient allocation;
- closest mechanisms combining these ideas;
- a dated feature comparison supporting any novelty statement.

## Method

Document:

- P0 boundary and freeze;
- 512x512 cover and 128x128 secret;
- Base/Detail split;
- header, RS, CRC, scrambling, and interleaving;
- exact 222,360-bit slot allocation;
- C0-C3 definitions;
- A feature score, allocation, and power mapping;
- D protection layout;
- semi-blind extraction;
- approved PDFB profile and transform fingerprint;
- clipping and half-up rounding.

## Experimental design

### Cases

List Baboon, Boat, Peppers, and House and the four fixed secret assignments.
Explain that exact article pairing is unknown.

### Core matrix

| Channel | Methods | Pairs | Rows |
|---|---:|---:|---:|
| Clean | 4 | 4 | 16 |
| JPEG Q=70 | 4 | 4 | 16 |
| Gaussian variance=10 | 4 | 4 | 16 |
| S&P density=0.03 | 4 | 4 | 16 |
| **Total** |  |  | **64** |

State that these 64 rows come from 16 saved embeddings and one deterministic
channel realization per pair and attack.

### Conditional hard checks

Explain the predeclared triggers and report which of JPEG 50, Gaussian 15, and
S&P 0.05 were run. Each triggered family adds eight C0/C3 rows. Total execution
cannot exceed 88 rows.

## Outcomes

Primary:

- per-case `C0-C3` effective unrecovered-bit rate under the three representative
  attack families.

Mechanism:

- A main effect;
- D main effect;
- A-by-D interaction.

Engineering:

- clean decode and CRC state;
- PSNR and SSIM;
- raw BER and layer recovery;
- capacity and lambda;
- runtime and memory.

## Analysis

Present:

- every raw scheduled value;
- per-case contrasts;
- mean, median, range, and direction count;
- all failures;
- trigger outcomes.

Do not present a four-case bootstrap, sign-flip, Wilcoxon, Holm family, or
achieved-power analysis as population evidence.

## Results structure

### Table 1 - contracts

P0 versus DIGITAL_A_D dimensions, payload, transform, extraction, and claim
boundaries.

### Table 2 - PDFB gate

Toolbox identity, band shapes, capacity, reconstruction, probe measures, and
human decision.

### Table 3 - four cases

Source identifiers, secret assignments, hashes, and preprocessing.

### Table 4 - clean validity

All 16 method-pair rows.

### Table 5 - core attacked results

All C0-C3 EUR values for the three representative attacks.

### Table 6 - mechanism contrasts

Per-case A, D, and A-by-D effects.

### Table 7 - conditional checks

Trigger status and any hard C0/C3 results.

### Figures

- one pipeline diagram;
- one per-case C0 versus C3 plot;
- one compact A/D/interaction plot;
- optional hard-severity plot only if triggered.

## Discussion paths

### Positive

State the exact cases, conditions, effect size, and consistency. Keep wording
case-bounded.

### Mixed

Explain pair or family heterogeneity without selecting favorable cells.

### Neutral

State that the bounded study did not show meaningful improvement. Do not expand
the matrix after the result.

### Negative

Use ablations to identify the likely harmful component and report the result as
valid evidence.

## Limitations

At minimum:

- four-case scope;
- exact author parameters and pairing are unavailable;
- secret-size mismatch with the source article;
- one deterministic channel realization per condition;
- semi-blind extraction;
- only three representative attack families;
- no geometric robustness or cryptographic-security evaluation;
- no population-level generalization.

## Reproducibility statement

Link every reported number to:

- research commit;
- PDFB evidence and transform fingerprint;
- four-row manifest;
- config hashes;
- 16 stego artifacts;
- 64-88 raw result rows;
- generated table or figure.

