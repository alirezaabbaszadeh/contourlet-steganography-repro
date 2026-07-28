# Manuscript blueprint

## Working title

Primary neutral title:

> Adaptive coefficient allocation and unequal Base/Detail protection for
> failure-aware digital image steganography: a controlled factorial study

Use "contourlet" in the title only after an approved contourlet runtime profile
supports the final experiment. Do not put "superior," "secure," or "robust" in
the title before the corresponding evidence exists.

## Manuscript identity

The paper should be framed as:

1. an independently audited foundation based on Kumar et al. (2026);
2. a new, separately specified digital A+D mechanism;
3. a controlled factorial evaluation that can attribute A, D, and their
   interaction;
4. a failure-aware and reproducible comparison, including negative results.

It is not a claim that the repository contains the authors' code.

## Candidate contribution statement

The intended contributions are:

1. a bit-exact Base/Detail transport with deterministic provenance and explicit
   decode failures;
2. adaptive coefficient allocation and power derived from energy, variance,
   entropy, and calibration-only stability;
3. unequal error protection that prioritizes the Base layer;
4. a C0-C3 factorial design separating A, D, and A-by-D effects;
5. a fail-closed transform gate and evidence contract;
6. paired, failure-aware analysis under fixed payload and distortion.

The final contribution list must remove any item that was not evaluated.

## Abstract structure

Write the abstract only after evidence lock:

1. **Problem:** robustness, imperceptibility, and payload are often compared
   under incompletely matched contracts.
2. **Method:** state cover/secret sizes, 0.5 bpp raw payload, 222,360-bit
   protected transport, A, D, and transform identity.
3. **Design:** state C0-C3 factorial, sample size, five seeds, nine attacks,
   matched PSNR, and primary outcome.
4. **Results:** insert generated effect, interval, failure rate, and interaction.
5. **Conclusion:** use the result-dependent wording below and state the claim
   boundary.

Do not lead with a p-value or only the best image.

## Section plan

### 1. Introduction

- define the practical steganographic recovery problem;
- explain why fixed payload, distortion, and failure accounting matter;
- distinguish incidental channel robustness from cryptographic security;
- identify the source article as motivation and baseline foundation;
- state the gap: no factorial attribution of adaptive placement and unequal
  semantic-layer protection under a reproducible digital contract;
- list bounded contributions and research questions.

### 2. Related work

Organize by mechanism, not by a long chronological list:

- transform-domain image steganography;
- contourlet and non-subsampled contourlet methods;
- adaptive coefficient selection and perceptual allocation;
- unequal error protection and semantic/base-enhancement layers;
- robust image transmission and failure-aware evaluation;
- reproducibility limitations in transform-domain comparisons.

Include a dated search protocol, databases, queries, inclusion criteria, and a
closest-method claim chart. The source article's reference list is a starting
point, not the complete novelty search.

### 3. Audit of the foundation

- summarize the source article's stated 4-level contourlet, high-frequency
  embedding, `alpha=0.15`, attacks, and headline metrics;
- show outcome-determining omissions and contradictions;
- describe P0 as an independent reconstruction;
- separate reported, interpreted, proxy, control, and reproduced;
- state why direct numeric equivalence is currently blocked.

Do not reproduce or adapt article figures unless the license and permission
permit it. Create original diagrams from repository contracts.

### 4. Proposed digital A+D method

#### 4.1 Preprocessing and bit planes

- 512x512 grayscale cover;
- 128x128 grayscale secret;
- Base = four MSBs, Detail = four LSBs;
- exact recombination and 0.5 bpp raw payload.

#### 4.2 Transport

- fixed header and CRC;
- RS profiles;
- deterministic scrambling and interleaving;
- exactly 222,360 bits.

#### 4.3 Adaptive component A

- subband energy, variance, 64-bin entropy, and calibration-only stability;
- robust normalization;
- score, capacity allocation, and power mapping;
- deterministic tie breaking.

#### 4.4 Unequal component D

- stronger Base and weaker Detail RS protection;
- Base-first placement in higher-score bands for C3;
- fixed round-robin control for C2.

#### 4.5 Embedding and extraction

- sign embedding equation;
- semi-blind coefficient difference;
- PSNR-constrained lambda;
- uint8 boundary;
- failure reporting.

#### 4.6 Transform profiles

- distinguish proxy, Haar control, and approved PDFB;
- report actual capacity and redundancy;
- state the human-reviewed transform gate result.

### 5. Experimental protocol

Reference the frozen protocol rather than rewriting it inconsistently:

- datasets and rights;
- splits and leakage prevention;
- sample-size rule;
- pair and seed schedule;
- C0-C3 factors;
- clean gate;
- nine final attacks;
- primary and secondary outcomes;
- exclusion policy;
- paired inference and multiplicity;
- hardware and runtime boundary.

### 6. Results

Report in this order:

1. transform and clean-gate outcomes;
2. data flow and execution completeness;
3. primary attack-averaged C3 versus C0 result;
4. A and D main effects and interaction;
5. per-attack heterogeneity;
6. Base versus Detail recovery;
7. failures and worst cases;
8. imperceptibility and payload checks;
9. runtime and memory;
10. ablations and sensitivity analyses.

Do not begin with only PSNR/SSIM.

### 7. Discussion

- interpret mechanism effects, not only rankings;
- explain positive and harmful interactions;
- compare only harmonized evidence;
- discuss payload-distortion-robustness trade-offs;
- state dependence on semi-blind cover access;
- discuss transform and dataset generalization;
- explain why deterministic transport randomization is not cryptographic
  encryption;
- retain negative findings and unresolved failures.

### 8. Limitations

At minimum:

- author-equivalent PDFB may remain unknown;
- the digital secret size differs from the source article;
- attacks are a finite incidental-channel suite;
- no steganalysis detector or cryptographic threat model is evaluated;
- grayscale and semi-blind assumptions limit generalization;
- timing is platform-dependent;
- dataset licenses may require acquisition rather than redistribution.

### 9. Conclusion

Use one of the result-dependent paths below. Do not promise future superiority.

### 10. Data and code availability

Provide:

- repository and immutable release;
- environment lock;
- input identifiers, acquisition scripts, and manifests;
- raw result and analysis archive;
- generated tables and figures;
- checksums and persistent archive identifier;
- explicit external-toolbox acquisition requirement.

## Planned tables

| Table | Content | Generated from |
|---|---|---|
| T1 | Source article versus P0 versus DIGITAL_A_D contracts | Configs and audit docs |
| T2 | C0-C3 factor definitions and fixed budgets | Digital config and allocation manifests |
| T3 | Data strata, splits, pairs, seeds, and rights | Source inventory and manifests |
| T4 | Transform capacity, reconstruction, redundancy, and gate status | Transform audit evidence |
| T5 | Primary attack-averaged C3-versus-C0 result | Primary analysis JSON |
| T6 | A, D, interaction, and pairwise secondary contrasts | `factorial.csv` |
| T7 | Per-attack recovery, failures, and worst cases | `results_long.csv` and summary |
| T8 | Base/Detail layer survival | Raw result rows |
| T9 | Imperceptibility, payload, lambda, time, and memory | Run artifacts |
| T10 | Ablations and sensitivity analyses | Separate preregistered runs |

Every table must show sample count and uncertainty where applicable.

## Planned figures

| Figure | Purpose |
|---|---|
| F1 | Original project diagram: P0, DIGITAL_A_D, transform gate, evaluation |
| F2 | Base/Detail transport and RS protection |
| F3 | C0-C3 factorial and estimands |
| F4 | Transform band inventory and candidate utilization |
| F5 | Pair-level primary C3-versus-C0 improvement with interval |
| F6 | Attack-by-method heatmap including failure-aware metric |
| F7 | Base versus Detail recovery across attack severity |
| F8 | Payload-distortion-robustness operating point or frontier |
| F9 | Failure-stage distribution |
| F10 | Reproducibility and claim-evidence flow |

Figures must be created from repository-authored code or original vector
diagrams. Do not copy source-article artwork.

## Required ablations

- C0, C1, C2, and C3;
- A without stability or with fixed equal features;
- D with Base/Detail protection swapped as a diagnostic, not a candidate;
- fixed versus adaptive placement at matched power;
- equal versus unequal protection at matched transport size;
- float coefficient control versus actual uint8 transmission;
- Haar engineering control versus approved PDFB profile;
- alternative PSNR operating points only if prospectively specified as a
  curve, not selected after final results.

## Result-dependent conclusion paths

### If the primary rule passes

Conclude that C3 produced a practically meaningful improvement over C0 under
the locked digital protocol. Attribute benefit to A, D, or interaction only
when their factorial estimates support that explanation.

### If direction is favorable but the rule fails

Conclude that the observed direction favored C3 but did not meet the
preregistered practical and statistical criteria. Report the interval and what
effects remain plausible.

### If effects are mixed

Conclude that A+D trades performance across channels or intensities. Describe
which mechanism and semantic layer drive the heterogeneity.

### If C3 is inferior

Conclude that the proposed combination did not improve recovery under the
locked design. Preserve the factorial analysis as evidence about why and use
future work, not post hoc retuning, for a new method version.

## Reviewer-risk checklist

Before submission, answer:

1. Is the comparison apples-to-apples in payload, distortion, and transform?
2. Is the source baseline author-equivalent or explicitly an interpretation?
3. Why is the pair the statistical unit?
4. How are decode failures counted?
5. Was the final attack or dataset selected after viewing results?
6. Is the primary outcome implemented exactly as preregistered?
7. Are repeated seeds handled without pseudoreplication?
8. Are all secondary tests corrected?
9. Is A+D technically different from a parameter sweep?
10. Are security terms supported by a threat model?
11. Can every table value be regenerated?
12. Are neutral and negative outcomes visible?

## Citation and terminology

Use the official source citation:

> Kumar, R., Singhal, S. & Sharma, V. K. Efficient image steganography method
> using contourlet transform and geometric-based pixel encryption for enhanced
> security. Scientific Reports 16, 16771 (2026).
> https://doi.org/10.1038/s41598-026-41168-0

Use `effective unrecovered-bit rate`, `adaptive allocation and power`, and
`unequal protection` consistently. Reserve `encryption` for the source
article's terminology or a separately justified cryptographic construction.
