# Protocol for substantiating the proposed method

## Separate the claims

Technical novelty and empirical performance are different:

1. novelty requires a dated prior-art search and a feature-by-feature
   comparison;
2. performance requires a fair execution under the fixed DIGITAL_A_D contract.

Higher PSNR, SSIM, or recovery alone does not prove novelty.

## Frozen baseline

- P0 remains numerically frozen.
- Reported article values remain external targets.
- Every measured value must come from repository artifacts.
- Missing article parameters are stated as missing, not guessed and then called
  author-equivalent.

## Proposed contribution

The current proposal contains two experimental factors:

- `A`: adaptive coefficient allocation and power;
- `D`: unequal Base/Detail protection.

The minimum meaningful ablation is C0-C3. Additional method variants are not
scheduled unless they test a distinct, predeclared mechanism claim.

## Fair comparison controls

Hold constant across C0-C3:

- four cover-secret pairs;
- 222,360 protected bits;
- `45.0 ± 0.1 dB` stego PSNR;
- approved PDFB profile and coefficient pool;
- preprocessing and uint8 boundary;
- deterministic channel realization;
- metric and failure definitions;
- hardware and timing boundary.

The internal deterministic value used by scrambling or noise generation is not
an experimental seed factor.

## Bounded evidence design

Use the four source-image traceability cases:

- Baboon;
- Boat;
- Peppers;
- House.

The mandatory conditions are:

- Clean;
- JPEG Q=70;
- Gaussian variance=10;
- salt-and-pepper density=0.03.

This yields 64 rows from 16 embeddings. Predeclared hard checks can add at most
24 C0/C3 rows. The absolute cap is 88.

Do not schedule:

- repeated seeds;
- an automatic larger dataset;
- Q=90, Gaussian 5, or S&P 0.01;
- C1/C2 at hard severity;
- rotation or crop for DIGITAL_A_D;
- post-result parameter searches.

## Outcomes

Primary bounded outcome:

- per-case `C0-C3` effective unrecovered-bit rate under the three
  representative attack families.

Mechanism outcomes:

- A main effect;
- D main effect;
- A-by-D interaction.

Engineering outcomes:

- PSNR and SSIM;
- BER and layer recovery;
- header and payload CRC state;
- capacity and selected lambda;
- runtime and memory.

All failures remain outcomes.

## Analysis

For four cases, publish raw values and report mean, median, range, and direction
count. Do not present repeated-seed averaging, power analysis, large-resample
bootstrap, permutation p-values, Wilcoxon, or Holm correction as required
evidence for this bounded study.

If a future paper seeks population-level generalization, it must define and
fund a separate protocol before collecting those outcomes.

## Novelty evidence

A novelty statement requires:

- search date and databases;
- search terms and inclusion rules;
- closest prior methods;
- feature chart covering A, D, digital transport, payload matching, and
  extraction assumptions;
- the precise mechanism difference;
- C0-C3 evidence showing whether A and D matter;
- limitations and known combinations.

Allowed wording is limited to the documented search scope and date.

## Security boundary

Scrambling, interleaving, AP/GP/HP, histogram similarity, and robustness to
incidental corruption do not establish cryptographic security. A security claim
requires a separate keyed design, threat model, and direct analysis.

## Evidence package

Archive:

- frozen code and P0 hashes;
- MATLAB PDFB evidence and human review;
- four-row manifest and input hashes;
- exact configs;
- 16 stego artifacts;
- 64-88 raw rows;
- conditional trigger records;
- generated tables and figures;
- prior-art claim chart;
- neutral and negative results.

The final claim wording must pass
[`CLAIMS_AND_EVIDENCE.md`](CLAIMS_AND_EVIDENCE.md) and
[`CLAIM_EVIDENCE_MATRIX.csv`](CLAIM_EVIDENCE_MATRIX.csv).

