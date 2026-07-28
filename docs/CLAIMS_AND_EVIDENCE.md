# Claims and evidence policy

## Purpose

This document prevents claim inflation. Every manuscript statement about
reproduction, robustness, novelty, superiority, or security must identify:

- the exact experiment contract;
- the transform identity;
- the data and observational unit;
- the supporting artifact;
- the uncertainty and failure policy;
- the limitation that bounds the statement.

The machine-readable companion is
[`CLAIM_EVIDENCE_MATRIX.csv`](CLAIM_EVIDENCE_MATRIX.csv).

## Vocabulary

| Term | Meaning in this project |
|---|---|
| reported | Printed by the source article |
| implemented | Present in repository code |
| tested | Covered by deterministic automated tests |
| measured | Produced by an identified runtime execution |
| reproduced | Independently measured under matched outcome-determining conditions |
| interpreted | A necessary choice not disclosed by the source |
| proxy | A transparent substitute, not the claimed transform |
| control | A profile used to test software or mechanism behavior |
| supported | Minimum evidence for the bounded claim is present |
| blocked | Required evidence is missing |
| prohibited | The current design cannot support the claim |

`Implemented` is not a synonym for `measured`, and `measured` is not a synonym
for `reproduced`.

## Claim ladder

### Level 0 - Source traceability

Allowed:

> Kumar et al. report an average cover/stego PSNR of 45.5 dB under their
> described experiments.

Required: citation and `PAPER_TARGETS.csv`.

Not allowed:

> We obtained 45.5 dB.

unless a repository run actually produced that value under an identified
contract.

### Level 1 - Internal software validity

Allowed after tests pass:

> The repository's digital format round-trips exactly before channel
> corruption, and its artifacts are deterministic for fixed inputs and seed.

Required: tests, commit, config, CI, and P0 freeze.

This level says nothing about contourlet fidelity or empirical superiority.

### Level 2 - Engineering-control evidence

Allowed:

> C0-C3 execute under the `haar_orthogonal_control_v1` engineering control.

Required: transform audit, clean runs, and artifacts.

Not allowed:

> The contourlet implementation passes.

Haar is not a contourlet transform.

### Level 3 - Explicit PDFB interpretation

Allowed only after Stage 0 runtime pass and human review:

> Under the explicitly specified Minh Do Contourlet Toolbox profile using
> `9-7`, `pkva`, and `[2,2,2,2]`, the measured transform satisfied the
> repository's capacity, reconstruction, and writability gates.

Not allowed:

> We reproduced the authors' contourlet transform.

The source paper does not disclose enough parameters to identify equivalence.

### Level 4 - Mechanism evidence

Allowed after the locked factorial study:

> Under the controlled digital protocol, the estimated A main effect was ...

Equivalent bounded language applies to D and A-by-D interaction.

Required: locked manifests, transform, config, all four methods, raw rows,
pair-level analysis, uncertainty, failures, and multiplicity correction.

### Level 5 - Controlled superiority

Allowed only if the primary rule in
[`RESEARCH_PROTOCOL.md`](RESEARCH_PROTOCOL.md) passes:

> Under the preregistered nine-attack digital protocol, C3 reduced the
> attack-averaged effective unrecovered-bit rate relative to C0 by [effect],
> with [interval], exceeding the 0.01 practical threshold.

The sentence must include the protocol boundary. It cannot be shortened to
"C3 is superior" without context.

### Level 6 - Direct article comparison

This claim is blocked until one of these paths is complete:

1. author code and exact parameters are obtained and verified; or
2. a human-approved explicit PDFB interpretation is used for both methods
   under a harmonized payload, data, attack, quantization, and metric contract.

Even then, if author equivalence remains unknown, use:

> C3 outperformed our explicit reconstruction under the harmonized protocol.

Do not use:

> C3 proved superior to Kumar et al.

### Level 7 - Novelty

Empirical performance does not prove novelty. A technical novelty statement
requires:

- a dated search strategy and databases;
- closest-prior-art selection;
- claim-by-claim feature chart;
- a precise mechanism absent from the closest methods;
- ablations showing that the claimed component is outcome-relevant;
- disclosure of known combinations and limitations.

Permitted wording is limited to the search scope and date.

### Level 8 - Security

The current protocol does not support cryptographic-security claims.
Deterministic scrambling, interleaving, AP/GP/HP, histogram similarity, PSNR,
SSIM, NCC, and robustness to incidental noise are not proofs of secrecy.

Prohibited wording includes:

- "cryptographically secure";
- "immune to steganalysis";
- "unbreakable";
- "secure against all attacks";
- "encryption" for the digital scrambler without an explicit terminological
  qualification.

## Current evidence status

| Claim | Status | Reason |
|---|---|---|
| Source article values are transcribed | supported | Audited targets and official citation exist |
| P0 is executable | supported | Tests and CI exist |
| P0 is author-equivalent | blocked | Transform and pseudocode details are missing |
| Digital format is deterministic | supported | Bitstream and pipeline tests exist |
| C0-C3 execute under Haar control | supported as engineering control | Deterministic transform and clean integration tests exist |
| Python directional proxy supports clean 222,360-bit recovery at 45 dB | negative evidence | Measured proxy path fails and is retained |
| MATLAB PDFB Stage 0 runtime passes | pending | Audit code exists; external runtime evidence does not |
| A improves recovery | pending | No final locked study |
| D improves recovery | pending | No final locked study |
| A and D have positive synergy | pending | No final locked study |
| C3 is superior to C0 | pending | Primary aggregate and locked data are absent |
| C3 is superior to the source article | blocked | Contracts are not harmonized |
| Digital scrambling provides cryptographic secrecy | prohibited | No key-based threat model or security proof |

## Decision rules for final wording

### Positive primary result

Report:

- absolute and relative effect;
- bootstrap interval;
- sign-flip and secondary corrected results;
- pair count and seed schedule;
- all failure rates;
- worst pair and attack;
- transform and payload boundary.

Use "supported under the locked protocol," not "proved universally."

### Neutral or inconclusive result

Report:

- effect and interval;
- whether the interval includes practically useful and harmful effects;
- achieved power and failure patterns;
- which secondary mechanisms were informative.

Do not rewrite the primary endpoint or promote a favorable secondary attack.

### Negative result

Report:

- where C3 lost performance;
- whether A, D, or interaction caused the loss;
- complexity and distortion trade-offs;
- design changes as future work on new development data.

A negative result is a valid contribution when the protocol and artifacts are
strong.

### Mixed result

If C3 helps some attacks and harms others, state heterogeneity. A global claim
depends on the primary aggregate rule, not the most favorable cell.

## Evidence citation inside the manuscript

Every generated number should be traceable to:

```text
experiment commit
  -> config and manifest hashes
  -> run ID and raw results row
  -> analysis ID
  -> generated table or figure
```

Hand-copied table values are prohibited. Reported source-paper values must be
labelled `reported_not_reproduced`.

## Claim review checklist

Before accepting a sentence:

1. Is the subject P0, Haar, explicit PDFB, or digital C0-C3?
2. Is the payload contract stated or implied correctly?
3. Does the evidence exist on a published commit?
4. Are failures included?
5. Does the interval support the direction and practical size?
6. Is the statement limited to the tested attacks and data?
7. Is "reproduced," "novel," "secure," or "proved" being used beyond its
   definition?
8. Does the claim/evidence CSV show `supported` for this exact claim?
