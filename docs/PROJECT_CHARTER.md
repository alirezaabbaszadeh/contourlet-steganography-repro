# Project charter

## Mission

Produce a bounded, auditable research result for the DIGITAL_A_D method using
the smallest execution set that can still separate A, D, their interaction,
and the full C3 method.

The project is not a production service and is not a population-scale image
benchmark.

## Two separate paths

| Path | Purpose | Boundary |
|---|---|---|
| P0 | independent reconstruction and source-paper traceability | numerically frozen; 512x512 analogue secret; AP/GP/HP and legacy geometric stress tests stay here |
| DIGITAL_A_D | controlled digital A+D study | 128x128 secret; fixed 222,360-bit transport; C0-C3; no geometric-robustness claim |

P0 results and DIGITAL_A_D results are never pooled.

## Method contract

| Method | Adaptive allocation and power A | Unequal protection D |
|---|---:|---:|
| C0_FIXED | off | off |
| C1_A | on | off |
| C2_D | off | on |
| C3_A_D | on | on |

All methods share the same inputs, approved transform, eligible pool, payload,
PSNR target, preprocessing, channel realization, and metrics.

## Fixed numerical contract

| Item | Value |
|---|---|
| Cover | grayscale 512x512 uint8 |
| Secret | grayscale 128x128 uint8 |
| Raw secret | 131,072 bits |
| Protected payload | exactly 222,360 bits |
| Header | fixed 127 bytes, RS(255,127), 2,040 encoded bits |
| PSNR target | `45.0 ± 0.1 dB` |
| Extraction | semi-blind with original cover |
| Core cases | Baboon, Boat, Peppers, House |
| Core channels | Clean, JPEG 70, Gaussian 10, S&P 0.03 |
| Conditional hard channels | JPEG 50, Gaussian 15, S&P 0.05 |
| Scientific seed repetitions | 0 |
| Mandatory result rows | 64 |
| Absolute result-row cap | 88 |

## Cost rule

An execution is allowed only when it directly supports one of these:

1. transform viability;
2. clean correctness;
3. A effect;
4. D effect;
5. A-by-D interaction;
6. C3 versus C0 at one representative condition per attack family;
7. a triggered hard-severity confirmation.

Q=90, Gaussian variance=5, S&P density=0.01, repeated seeds, automatic dataset
expansion, and inferential resampling are outside the current study.

## Evidence gates

| Gate | Required evidence | Failure action |
|---|---|---|
| P0 freeze | protected hashes and tests | stop |
| PDFB Stage 0 | raw MATLAB evidence, independent validation, human review | stop; do not substitute a proxy |
| Capacity | at least 222,360 eligible slots | stop; do not lower payload |
| Data lock | four fixed pairs, hashes, rights, preprocessing | stop |
| Run budget | 64 mandatory, no more than 88 total | reject plan |
| Clean | all C0-C3 rows retained and classified | stop attacked expansion on algorithmic failure |
| Conditional trigger | objective per-family trigger record | do not run untriggered family |
| Claim review | wording bounded to evidence | revise claim |

## Randomness policy

One deterministic realization is derived for each pair and attack and shared
across methods. Internal scrambling or noise-generation metadata may remain in
the implementation, but it is not an experiment factor and never multiplies
rows.

## Analysis policy

With four cases, report raw values and descriptive summaries:

- per-case C0-C3;
- A, D, and A-by-D contrasts;
- mean, median, range, and direction count;
- all failures;
- PSNR, SSIM, BER, EUR, CRC, runtime, and memory.

Do not require power analysis, bootstrap, sign-flip, Wilcoxon, or Holm
correction for this bounded case study.

## Claim boundary

Allowed:

> On the four source-image traceability cases and the named operating
> conditions, C3 showed [measured result] relative to C0.

Not allowed:

- universal superiority;
- author-equivalent reproduction without missing author parameters;
- robustness to untested attacks;
- population generalization;
- cryptographic-security claims;
- using a neutral result to justify an unplanned larger matrix.

## Change control

Any change to transform, payload, PSNR, pair assignments, core attacks,
conditional triggers, analysis, or the 88-row cap creates a new protocol
version. Additional cost requires an explicit written decision before results
are viewed.

