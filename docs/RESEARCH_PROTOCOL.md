# Lean prospective research protocol

## Status

Protocol version: `DIGITAL_A_D research protocol v2-lean`

This version supersedes the earlier large factorial plan. The study is a
bounded, source-image case study, not a population-level generalization study.
Every scheduled execution must support a named claim. Repeated random seeds,
power-driven sample expansion, and the full nine-level attack grid are not part
of the final protocol.

The source article used a small standard-image experiment and did not report a
multi-seed design. This protocol deliberately stays close to that evidence
scale while preserving the minimum ablation needed to identify the proposed
mechanism.

## Scientific scope

The study has four questions:

| ID | Question |
|---|---|
| RQ1 | Does adaptive allocation and power `A` help under one representative condition from each attack family? |
| RQ2 | Does unequal Base/Detail protection `D` help under the same conditions? |
| RQ3 | Is the joint A-by-D effect favorable or unfavorable? |
| RQ4 | Does the full C3 method improve recovery over C0 on the four source-image traceability cases? |

It does not estimate performance for a wider image population. It does not
claim robustness outside the explicitly tested channel conditions.

## Methods that must remain

All four methods are essential in the core matrix because they are the smallest
set that separates A, D, and their interaction.

| Method | A | D | Purpose |
|---|---:|---:|---|
| `C0_FIXED` | off | off | fixed symmetric control |
| `C1_A` | on | off | A-only ablation |
| `C2_D` | off | on | D-only ablation |
| `C3_A_D` | on | on | full method |

For lower-is-better effective unrecovered-bit rate (`EUR`), report these
descriptive contrasts for every pair and core channel:

| Estimand | Expression |
|---|---|
| A main effect | `((C0-C1) + (C2-C3)) / 2` |
| D main effect | `((C0-C2) + (C1-C3)) / 2` |
| A-by-D interaction | `C1 + C2 - C0 - C3` |
| Full method improvement | `C0-C3` |

Positive values favor the named component or C3.

## Evidence cases

The mandatory study uses four identifiable standard covers discussed by the
source article:

- Baboon;
- Boat;
- Peppers;
- House.

Each cover is paired once with one predeclared 128x128 secret. Exact article
pairing is unknown, so this is described as a source-image traceability case
study and never as author-equivalent reproduction.

No automatic expansion to 50 or 100 pairs is allowed. A wider dataset is a
separate future study requiring a new protocol and budget.

## No repeated-seed factor

There is exactly one channel realization per `pair_id + attack_id`. The
realization identifier is derived deterministically from the locked protocol,
pair, and attack identifiers and is shared across C0-C3. It is not a tunable
factor and does not create repeated rows.

The format's internal deterministic value used for scrambling, interleaving,
or reproducible noise generation may remain in code. It is implementation
metadata, not an experiment axis. There is no seed list, seed sweep, or
within-pair seed averaging.

## Fixed operating point

Every method uses:

- cover: grayscale 512x512 uint8;
- secret: grayscale 128x128 uint8;
- Base/Detail split: four bit planes each;
- raw secret: 131,072 bits;
- protected embedded payload: exactly 222,360 bits;
- the same approved PDFB transform and eligible coefficient pool;
- stego PSNR target: `45.0 ± 0.1 dB`;
- identical preprocessing, rounding, clipping, attack implementation, and
  channel realization within each paired comparison;
- semi-blind extraction with the original cover.

Payload, PSNR, ECC, or transform identity may not be relaxed to make a method
pass.

## Mandatory core matrix

One medium, discriminating severity is retained from each relevant attack
family. Clean is required as the validity gate.

In each method cell below, `4` means one evaluation for each of the four
traceability pairs.

| Channel condition | C0 | C1 | C2 | C3 | Rows |
|---|---:|---:|---:|---:|---:|
| Clean | 4 | 4 | 4 | 4 | 16 |
| JPEG Q=70 | 4 | 4 | 4 | 4 | 16 |
| Gaussian variance=10 | 4 | 4 | 4 | 4 | 16 |
| Salt-and-pepper density=0.03 | 4 | 4 | 4 | 4 | 16 |
| **Mandatory total** | **16** | **16** | **16** | **16** | **64** |

The core requires only 16 embeddings: four pairs times four methods. The saved
stego artifacts are reused for clean extraction and the three attacked channel
evaluations.

## Conditional hard-severity checks

Low-severity points `JPEG 90`, `Gaussian 5`, and `salt-and-pepper 0.01` are
removed because they add cost while usually producing little discrimination.

Hard points are not automatic. For each attack family separately, run the hard
point only if all gates pass and at least one of these predeclared conditions is
true:

1. the medium point is saturated for both C0 and C3, so it cannot distinguish
   the methods; or
2. C3 improves EUR over C0 by at least `0.01` in at least three of the four
   pairs and a harder confirmation is needed.

Only C0 and C3 are needed at this stage; C1 and C2 already served their
mechanism role in the core matrix.

| Conditional channel | C0 | C3 | Added rows |
|---|---:|---:|---:|
| JPEG Q=50 | 4 | 4 | 8 |
| Gaussian variance=15 | 4 | 4 | 8 |
| Salt-and-pepper density=0.05 | 4 | 4 | 8 |
| **Maximum conditional addition** | **12** | **12** | **24** |

The final study therefore contains:

- mandatory: 64 evaluation rows;
- conditional: 0, 8, 16, or 24 rows;
- absolute cap: 88 evaluation rows;
- embeddings: 16 total, with no new embedding required for the conditional
  C0/C3 checks.

Any proposal to exceed 88 rows requires a new written decision, a new claim
that needs those rows, and explicit budget approval.

## Outcomes and analysis

The primary outcome is `effective_unrecovered_bit_rate`, which gives no credit
to unknown bits after RS or CRC failure.

Because there are only four traceability cases, the final report is
descriptive:

- retain every raw pair-method-channel row;
- show `C0-C3` for each pair and attack family;
- report mean, median, range, and direction count;
- show A, D, and A-by-D contrasts per pair;
- report clean PSNR, SSIM, capacity, decode status, CRC status, runtime, and
  peak memory;
- report all algorithmic failures as outcomes.

Bootstrap, sign-flip, Wilcoxon, Holm correction, and achieved-power claims are
not required for this bounded case study. They may be used only in a future
larger protocol with an independently approved budget.

## Decision rule and allowed wording

C3 may be described as favorable in the bounded study only if:

1. C0-C3 all pass clean decode on all four pairs;
2. mean core attacked `C0-C3` EUR improvement is at least `0.01`;
3. the direction favors C3 on at least three of four pairs in at least two of
   the three attack families;
4. no outcome-driven tuning or selective rerun occurred.

Allowed wording:

> On the four source-image traceability cases, at the fixed payload and PSNR
> operating point, C3 improved recovery over C0 under [named conditions].

Prohibited wording:

- C3 is universally superior;
- the result generalizes to arbitrary images;
- the authors' exact implementation was reproduced;
- the method is robust to untested attacks;
- scrambling proves cryptographic security.

## Stop rules

Stop without expanding the matrix when:

- the PDFB Stage-0 or human-review gate fails;
- the approved transform has fewer than 222,360 eligible slots;
- a clean failure is algorithmic rather than an operational interruption;
- C3 shows no practically meaningful core advantage and the core is not
  saturated;
- the direct article-comparison contract cannot be harmonized.

A negative or neutral core result is a valid final result. It is not a reason
to add seeds, images, attacks, or retries.

## Operational retry policy

There are no scientific repetitions. A row may be rerun only after a documented
operational failure such as process interruption or corrupted output. The same
inputs and deterministic realization identifier must be reused, and the failed
artifact must remain in the audit trail.

## Required artifacts

Before execution:

- approved PDFB evidence and transform fingerprint;
- four-pair manifest and input hashes;
- fixed secret assignments;
- core and conditional attack profiles;
- protocol-lock file containing code, config, manifest, and analysis hashes;
- an automatic run-budget check that rejects more than 64 mandatory rows or
  more than 88 total rows.

After execution:

- immutable long-form results;
- saved 16 stego artifacts;
- trigger record for every conditional family, including families not run;
- descriptive tables and figures generated from raw rows;
- updated claim/evidence matrix.

