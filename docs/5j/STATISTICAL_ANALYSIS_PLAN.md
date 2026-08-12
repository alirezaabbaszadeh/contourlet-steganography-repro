# 5J Statistical Analysis Plan

Status: implementation baseline; freeze required before final-run unblinding  
Protocol: `FINAL-5J-v1`

## 1. Analysis population

The primary experimental unit is the image pair. Attack realizations are repeated observations within pair–method–severity cells and are not independent image samples.

The primary analysis set includes all preregistered final-study pairs and all scientific evaluations that completed under the locked contract. Scientific failures remain in the analysis. Operational failures are retained, reported separately, and handled through the missingness rules below.

## 2. Primary endpoints

1. Complete Recovery Rate.
2. Valid Base-only Recovery Rate.
3. Paired C3 minus C0 effect.
4. Paired C3 minus C3_NP effect, isolating Base-first placement.
5. Paired C3 minus B1 and C3 minus B2 effects on common endpoints.
6. Comparative failure-severity gap among evaluations without complete recovery.

The primary comparison family is:

- C3 vs C0;
- C3 vs C3_NP;
- C3 vs B1;
- C3 vs B2.

Holm correction is applied within each preregistered endpoint/attack-family comparison family. Unadjusted and adjusted values must both be reported alongside effect sizes and confidence intervals.

## 3. Secondary endpoints

- recovered protected-payload and raw-secret fractions;
- Base and Detail BER and recovery fractions;
- ECC failed-codeword count and overload summaries;
- reconstruction PSNR, SSIM, MSE, and NCC;
- cover–stego PSNR/SSIM;
- runtime, peak memory, throughput, and cache behavior;
- payload-sweep and PSNR-sweep response curves;
- failure-stage distribution;
- operational-failure rate.

## 4. Aggregation hierarchy

For stochastic attacks:

1. retain every realization-level raw row;
2. summarize realizations within each pair–method–attack–severity cell;
3. perform primary pair-level comparisons on those cell summaries;
4. use pair-cluster resampling when realization-level modeling is required.

Default cell summaries:

- binary endpoints: proportion across preregistered realizations;
- continuous bounded fractions/BER: mean plus median and range;
- runtime: median plus IQR;
- ECC overload: median, maximum, and sum.

Deterministic Clean and JPEG cells contain one observation per pair and method.

## 5. Effect reporting

Every primary comparison reports:

- paired absolute difference;
- paired relative difference where the denominator is well-defined;
- mean and median paired effect;
- standard deviation and IQR;
- minimum and maximum;
- direction count: improved, tied, worsened;
- 95% pair-cluster bootstrap confidence interval;
- endpoint-appropriate paired test;
- Holm-adjusted significance value for the primary family.

P-values never replace effect sizes or uncertainty intervals.

## 6. Endpoint-specific methods

### Binary recovery

Report paired proportions and paired differences. Use an exact or asymptotic paired binary test only when its assumptions and cell counts are adequate; otherwise emphasize bootstrap intervals and descriptive paired counts.

### Recovery fractions, BER, quality, runtime, and overload

Report paired distributions. Use a paired nonparametric or robust method if distributional assumptions are not supported. No transformation or alternative test may be selected based on which yields a favorable result.

### Failure stages

Report stage distributions and paired transition tables. Stage codes are ordered descriptors but not assumed to be equally spaced. Do not compute a simple arithmetic mean of stage numbers as the primary severity statistic.

## 7. Boundary and sweep analyses

For each attack family, plot and tabulate endpoint changes by preregistered severity. Interpolation is descriptive only; no untested threshold is claimed as observed.

Payload and PSNR sweeps are analyzed on the preregistered 10-pair subset for C0, C3_NP, and C3. Report within-pair curves and paired operating-point differences. The main-matrix 100% payload and 45.0 dB points are reused analytically; they are not duplicate incremental executions.

## 8. Operational failures and missing data

Every expected cell must exist in the run plan. Missingness receives one typed reason:

- `missing_operational`;
- `not_evaluated` because a prerequisite scientific stage was unreachable;
- `not_applicable` for unsupported method semantics;
- protocol violation.

Primary analysis includes all completed scientific outcomes. A sensitivity analysis may exclude documented operational failures only; it may not exclude scientific failures, unfavorable images, or extreme but valid attack outcomes.

A protocol violation is reported and quarantined; it is never silently repaired or substituted.

For a preregistered baseline cell whose frozen clean-embedding prerequisite is scientifically infeasible, the embedding and all dependent evaluation cells remain in the planned matrix. The embedding is a scientific failure; dependent evaluations are typed `not_evaluated` scientific failures rather than `missing_operational`. Failure-stage/completeness summaries retain those cells. Numeric recovery or reconstruction endpoints that were never observed remain unavailable and are not assigned zero, imputed, or replaced. Paired numeric summaries use only pairs for which that endpoint is defined and must report the defined-pair count alongside the effect.

## 9. Multiplicity and exploratory analyses

Primary endpoints and comparisons are preregistered. Secondary analyses are identified as secondary. Any analysis invented after unblinding is labelled exploratory and cannot replace a preregistered result.

No additional pair, method, seed, severity, or favorable subgroup may be added after outcome inspection without a new protocol revision and run identity.

## 10. Reproducible outputs

The analysis pipeline must generate directly from validated raw rows:

- completeness report;
- descriptive tables;
- paired-effect tables;
- adjusted primary-comparison table;
- attack-boundary curves;
- failure-stage transition tables;
- ECC-overload figures;
- payload and PSNR trade-off figures;
- runtime and memory summaries;
- manuscript-ready LaTeX/CSV tables and figure provenance.

No final numerical value may be hand-copied into the manuscript.

## 11. Freeze gate

Before the five-pair pilot is unblinded, record:

- exact analysis commit;
- software environment;
- bootstrap seed and replication count;
- endpoint transformations, if any;
- test choices and fallbacks;
- Holm comparison families;
- table and figure inventory;
- missingness rules.

Changes after freeze require a documented amendment that states whether it was made before or after outcome access.
