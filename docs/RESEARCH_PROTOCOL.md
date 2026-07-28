# Prospective research protocol

## Status

Protocol version: `DIGITAL_A_D research protocol v1`

This document is prospective. It defines the final study before the locked
test run. Software support for the per-attack factorial analysis exists. The
attack-averaged primary estimator defined below must be implemented, tested,
and frozen before the final data manifest is opened for analysis.

Any change after data lock is a protocol deviation and must be recorded with:

- the time and reason;
- whether any locked outcome had been inspected;
- affected configurations and commits;
- the original and changed analyses shown side by side.

## Relationship to the source article

The source article reports a 512x512 cover and a 512x512 secret, a fourth-level
contourlet decomposition, high-frequency embedding, and `alpha=0.15`. It does
not disclose enough transform and datatype details for author-equivalent
execution.

The controlled digital study uses a 512x512 cover and a 128x128 uint8
grayscale secret whose bit planes form the digital payload. It is therefore
not a raw reproduction of the article's payload contract. There are two
permitted comparison paths:

1. make claims about A, D, and A-by-D within the controlled digital protocol;
2. after an approved PDFB adapter and a harmonized baseline exist, make a
   separately qualified comparison with the article reconstruction.

The first path is the primary study. The second is conditional.

## Research questions

| ID | Question |
|---|---|
| RQ1 | Does adaptive allocation and power `A` improve recovery relative to fixed allocation? |
| RQ2 | Does unequal Base/Detail protection `D` improve recovery relative to symmetric protection? |
| RQ3 | Is the joint effect of A and D larger or smaller than the sum of their separate effects? |
| RQ4 | Does the full C3 method produce a practically meaningful recovery improvement over C0? |
| RQ5 | Under which attack types and intensities do Base and Detail fail differently? |

## Methods and factorial estimands

Let lower unrecovered-bit rate be better. The oriented method contrasts are:

| Estimand | Pair-level expression |
|---|---|
| A main effect | `((C0-C1) + (C2-C3)) / 2` |
| D main effect | `((C0-C2) + (C1-C3)) / 2` |
| A-by-D interaction | `C1 + C2 - C0 - C3` |
| Full method | `C0-C3` |
| A-only | `C0-C1` |
| D-only | `C0-C2` |
| D added after A | `C1-C3` |
| A added after D | `C2-C3` |

The executable statistics module stores equivalent oriented contrasts with
positive improvement. Sign conventions must be verified in a unit test for
the aggregate analysis before lock.

## Experimental unit

The independent observational unit is one unique cover-secret pair. A seed is
not an independent sample. If a pair is run under multiple seeds, values are
first averaged within pair, method, attack, and metric.

The final sample size is:

```text
N_final = max(50, N_required_by_preregistered_power_analysis)
```

The power calculation must target the primary minimum important difference,
use development or pilot variance only, target at least 80% power, and be
committed before the locked-test manifest is revealed to the analysis code.

## Fixed inputs and operating point

All C0-C3 runs share:

- the same cover-secret pair and seed;
- Pillow `L` grayscale conversion;
- bicubic resize to 512x512 cover and 128x128 secret;
- four-bit Base and four-bit Detail split;
- 131,072 raw secret bits;
- exactly 222,360 protected embedded bits;
- the same transform profile and eligible coefficient pool;
- the same PSNR target of 45.0 dB with 0.1 dB tolerance;
- half-up rounding, clipping, and uint8 transmission boundary;
- the same attack parameters and stochastic random realization for a given
  pair, seed, and attack contract;
- the same metric and analysis implementation.

The lambda search may select different feasible amplitudes for methods because
their coefficient weights differ. It may not relax the PSNR target.

## Primary outcome

The primary metric is `effective_unrecovered_bit_rate` because it assigns no
credit to unknown bits after RS or CRC failure.

For pair `i`, method `m`, attack `a`, and repeated seed `s`:

```text
E(i,m,a) = mean_s EUR(i,m,a,s)
P(i,m)   = (1/9) * sum_a E(i,m,a)
Delta(i) = P(i,C0_FIXED) - P(i,C3_A_D)
```

The nine equally weighted attacks are:

- JPEG quality 90, 70, and 50;
- Gaussian variance 5, 10, and 15;
- salt-and-pepper density 0.01, 0.03, and 0.05.

Positive `Delta` means C3 recovers more of the secret than C0.

### Minimum important difference

The practical threshold is an absolute reduction of `0.01` in the
attack-averaged effective unrecovered-bit rate. This is approximately 1,311 of
the 131,072 raw secret bits.

### Primary superiority rule

The paper may state that C3 is superior to C0 for the controlled digital final
suite only when all of these hold:

1. every method passes the clean-decode gate on all locked pairs;
2. the mean paired `Delta` is at least `0.01`;
3. the paired-bootstrap 95% confidence interval has lower bound greater than
   zero;
4. the two-sided paired sign-flip test has `p < 0.05`;
5. no protocol deviation capable of favoring C3 occurred after lock.

Because there is one declared primary contrast, it is not included in the
secondary multiplicity family. All components are reported even when the rule
is not met.

## Secondary outcomes

Secondary outcomes include:

- per-attack `effective_unrecovered_bit_rate`;
- A and D main effects and A-by-D interaction;
- decode success, header validity, and payload CRC validity;
- raw channel BER;
- Base and Detail BER when the corresponding layer is valid;
- known-bit fraction and correct-recovered-bit fraction;
- clean stego PSNR and windowed SSIM;
- eligible capacity, utilization, and selected lambda;
- wall-clock time and peak memory as descriptive engineering outcomes.

All per-attack and per-metric secondary contrasts are corrected as one
predefined family with Holm's method. Mean, median, standard deviation, paired
bootstrap interval, sign-flip result, Wilcoxon result, rank-biserial effect,
sample count, failure count, and worst case are retained.

Secondary findings may explain the primary result. They do not rescue a failed
primary superiority rule.

## Threat model and claim boundary

The decoder is semi-blind and has the original cover. The evaluated channel
applies non-targeted JPEG, additive Gaussian noise, or salt-and-pepper noise
under the exact repository implementation.

The study does not evaluate:

- confidentiality against a cryptographic adversary;
- chosen-cover, known-cover, or key-recovery attacks;
- steganalysis detection error;
- malicious coefficient-aware removal;
- geometric desynchronization in the digital path;
- network metadata or side-channel leakage.

Scrambling and interleaving are deterministic transport randomization. They
must not be described as standard encryption.

## Calibration and tuning

Only rows whose split begins with `calibration` may produce the stability
profile. Calibration uses JPEG 70, Gaussian variance 10, and salt-and-pepper
density 0.03. The artifact is bound to a transform fingerprint.

Development and pilot data may be used to:

- diagnose software errors;
- choose from a prospectively listed transform interpretation;
- perform the sample-size power calculation;
- confirm that output schemas and failure reporting work.

They may not be used to:

- choose a final attack after observing which favors C3;
- change the 0.01 primary threshold;
- remove hard images;
- alter Base/Detail ECC after comparing locked outcomes;
- tune the final profile on locked-test results.

## Exclusion and failure policy

Algorithmic failure is an outcome, not an exclusion.

An execution unit may be excluded only for an operational reason unrelated to
method performance, such as:

- unreadable or hash-mismatched input;
- process interruption before any method completed;
- corrupted output archive;
- confirmed implementation defect that invalidates all affected methods.

Every exclusion requires a reason and an audit record. If a defect can affect
relative performance, the complete final study is versioned and rerun. A
single failed method is not removed while retaining the other methods from the
same pair.

## Randomness

The planned final seed set is:

```text
2026, 2027, 2028, 2029, 2030
```

The same pair and seed are reused across all methods. Stochastic attack
realizations are deterministic functions of the recorded seed. Five seeds
reduce dependence on one random corruption while pair-level averaging avoids
pseudoreplication.

Changing the seed set after locked outcomes are visible creates a new protocol
version.

## Execution order

1. verify P0 freeze and all tests;
2. pass and review the selected transform gate;
3. freeze acquisition scripts and data policy;
4. generate and hash calibration, pilot, and locked manifests;
5. create transform-matched calibration stability;
6. pass clean C0-C3 on development data;
7. freeze code, config, manifests, seeds, and analysis;
8. execute the full locked benchmark once;
9. run the primary aggregate and secondary factorial analyses;
10. generate tables and figures from raw artifacts;
11. update the claim/evidence matrix before drafting conclusions.

## Result interpretation

| Outcome | Permitted conclusion |
|---|---|
| Primary rule passes | C3 improved attack-averaged recovery over C0 under the locked digital protocol |
| Mean positive but below 0.01 | Directionally favorable, not practically superior by the preregistered rule |
| Interval crosses zero | Evidence is inconclusive at the achieved sample size |
| C3 is worse | C3 did not improve and may reduce recovery under this protocol |
| Mixed per-attack effects | Report heterogeneity; do not select only favorable attacks |
| PDFB gate fails | Report transform incompatibility; Haar remains an engineering control |

No empirical outcome proves universal superiority or technical novelty.

## Required implementation before data lock

- add a tested attack-averaged primary-analysis command;
- add a manifest preflight for split leakage, duplicate content, and planned
  seeds;
- add a machine-readable protocol-lock artifact containing config, manifest,
  stability, code, and analysis hashes;
- add table and figure generation from immutable result files;
- run a dry-run with synthetic or pilot data only.
