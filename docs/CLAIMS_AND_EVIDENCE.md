# Claims and evidence policy

## Purpose

Every manuscript statement must stay within the evidence actually produced.
The current final design is a four-case traceability study with 64 mandatory
rows and at most 24 conditional rows. It is not a population-level benchmark.

The machine-readable companion is
[`CLAIM_EVIDENCE_MATRIX.csv`](CLAIM_EVIDENCE_MATRIX.csv).

## Vocabulary

| Term | Meaning |
|---|---|
| reported | printed by the source article |
| implemented | present in repository code |
| tested | covered by deterministic software tests |
| measured | produced by an identified runtime execution |
| reproduced | independently measured under matched outcome-determining conditions |
| interpreted | a necessary choice not disclosed by the source |
| proxy | a transparent substitute, not the claimed transform |
| case-supported | supported only on the four named traceability cases |
| blocked | required evidence is missing |
| prohibited | the design cannot support the claim |

Implemented is not measured, and measured is not author-equivalent
reproduction.

## Evidence ladder

### Level 0 - source reporting

Permitted:

> Kumar et al. report the values listed in `PAPER_TARGETS.csv`.

Do not rewrite a reported source value as a value obtained by this repository.

### Level 1 - software validity

Permitted after tests pass:

> The digital format round-trips exactly before channel corruption for fixed
> inputs and deterministic implementation metadata.

This says nothing about PDFB fidelity or empirical superiority.

### Level 2 - engineering control

Haar and the Python directional proxy may be reported only as engineering
controls. They are not contourlet evidence.

### Level 3 - explicit PDFB interpretation

After the real MATLAB Stage-0 pass and human review, permitted wording is:

> Under the explicit `9-7`, `pkva`, `[2,2,2,2]` profile, the measured transform
> passed the recorded structure, capacity, reconstruction, and writability
> gates.

Do not call this author-equivalent unless the missing author parameters are
obtained.

### Level 4 - mechanism evidence

After the 64-row core, A, D, and A-by-D may be described only for the four
named cases and four core channel conditions. Required evidence:

- all C0-C3 raw rows;
- fixed payload and PSNR;
- the approved transform fingerprint;
- per-case contrasts;
- failures and provenance;
- no repeated-seed or selective-rerun expansion.

### Level 5 - bounded C3 versus C0 result

If the decision rule in [`RESEARCH_PROTOCOL.md`](RESEARCH_PROTOCOL.md) passes:

> On the four source-image traceability cases, at the fixed operating point,
> C3 improved recovery over C0 under [named channel conditions].

Do not shorten this to "C3 is superior" or imply image-population
generalization.

### Level 6 - direct article comparison

This remains blocked until transform, payload, image pairing, attacks,
quantization, and metrics are harmonized. If exact author equivalence remains
unknown, use:

> C3 was compared with our explicit reconstruction under a harmonized
> contract.

### Level 7 - novelty

Performance does not prove novelty. A novelty statement requires a dated
literature search, closest-prior-art chart, precise mechanism difference, and
the C0-C3 ablation evidence.

### Level 8 - security

Scrambling, interleaving, AP/GP/HP, histogram similarity, PSNR, and robustness
to incidental noise do not establish cryptographic secrecy. "Unbreakable",
"cryptographically secure", and "immune to steganalysis" are prohibited.

## Required result reporting

Always report:

- all four case identifiers;
- every raw scheduled row;
- method and channel failures;
- per-case A, D, A-by-D, and C0-C3 values;
- mean, median, range, and direction count;
- fixed payload, PSNR, transform, and extraction boundary;
- whether each optional hard family was triggered.

Do not require or present population-level p-values, achieved power, or
confidence claims from four cases.

## Positive, mixed, neutral, and negative outcomes

### Positive

State the exact cases and conditions. Report the effect size and consistency
without universal wording.

### Mixed

State which pairs or attack families improved and which worsened. Do not select
only favorable cells.

### Neutral

Report that the bounded evidence did not show a practically meaningful
improvement. Do not add seeds or attack levels after seeing the result.

### Negative

Use C0-C3 ablations to identify whether A, D, or their interaction likely
caused the loss. A negative result is complete evidence and ends the current
execution plan.

## Evidence chain

Every number must trace through:

```text
research commit
  -> PDFB evidence and transform fingerprint
  -> four-row manifest and config hashes
  -> run ID and raw result row
  -> generated table or figure
```

Hand-copied result tables are prohibited.

## Claim review checklist

1. Is the subject P0, an engineering control, explicit PDFB, or DIGITAL_A_D?
2. Is the payload and PSNR contract correct?
3. Are the four cases and tested channels named or clearly bounded?
4. Does the supporting raw row exist?
5. Are failures retained?
6. Was the 64/88 run budget respected?
7. Is the statement avoiding population, universal, security, and
   author-equivalence inflation?
8. Does the machine-readable claim matrix permit this wording?

