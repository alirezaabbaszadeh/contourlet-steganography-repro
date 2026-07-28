# Research release checklist

This checklist controls a scientific release and manuscript submission. A box
is checked only from evidence, never from intention.

## Current blockers

- [ ] Run and review the external MATLAB PDFB Stage-0 gate.
- [ ] Implement a versioned PDFB embedding adapter after gate approval.
- [ ] Implement and test data duplicate/leakage preflight.
- [ ] Freeze a licensed independent dataset and manifests.
- [ ] Implement and test the attack-averaged primary analysis.
- [ ] Implement a protocol-lock artifact.
- [ ] Implement generated manuscript tables and figures.
- [ ] Execute the locked final experiment.

## A. Source and baseline

- [ ] Source article citation and version of record are correct.
- [ ] `PAPER_TARGETS.csv` matches the audit transcription.
- [ ] Every reported value is labelled `reported_not_reproduced`.
- [ ] P0 freeze passes for all six files.
- [ ] P0 changes, if any, are versioned rather than silently substituted.
- [ ] The manuscript states that this is not the authors' code.
- [ ] AP/GP/HP limitations and keyless behavior are disclosed.

## B. Transform

- [ ] Exact transform profile name is recorded.
- [ ] Pyramid and directional filters are recorded.
- [ ] Levels and directions per level are recorded.
- [ ] Every band shape and coefficient count is recorded.
- [ ] Total redundancy and candidate capacity are recorded.
- [ ] Candidate capacity is at least 222,360.
- [ ] Reconstruction error meets the locked tolerance.
- [ ] Coefficient writability probes pass.
- [ ] Runtime, toolbox paths, and hashes are recorded.
- [ ] Raw evidence and independent validation agree.
- [ ] Human review decision is versioned.
- [ ] No proxy or Haar result is described as author-equivalent PDFB.

## C. Digital format and methods

- [ ] Format version is fixed.
- [ ] Cover and secret dimensions are correct.
- [ ] Base/Detail split round-trips exactly.
- [ ] Header, CRC, RS, padding, and bit order match the format document.
- [ ] Protected payload is exactly 222,360 bits for every method.
- [ ] C0, C1, C2, and C3 definitions match the factorial contract.
- [ ] All coefficient slots are unique and map hashes are retained.
- [ ] Scrambling/interleaving seeds and permutation hashes are retained.
- [ ] No AP/GP/HP code enters DIGITAL_A_D.
- [ ] Clean decode succeeds for every method and locked pair.
- [ ] No recovered secret is fabricated after decode failure.

## D. Data

- [ ] Dataset names, versions, access dates, and rights are documented.
- [ ] Acquisition scripts are frozen.
- [ ] Source file and decoded-array hashes are stored.
- [ ] Calibration, pilot, locked-test, and traceability splits are disjoint.
- [ ] Exact and near-duplicate preflight passes.
- [ ] Pairing rule and pairing seed are frozen.
- [ ] Locked pair count satisfies `max(50, power requirement)`.
- [ ] Every locked pair has seeds 2026-2030.
- [ ] No hard image was removed based on method outcomes.
- [ ] Third-party images are not redistributed without permission.

## E. Protocol lock

- [ ] Research questions and hypotheses are frozen.
- [ ] Primary endpoint and 0.01 practical threshold are frozen.
- [ ] Secondary family and Holm correction are frozen.
- [ ] Attack suite and exact implementations are frozen.
- [ ] Exclusion and failure policy are frozen.
- [ ] Sample-size calculation is published.
- [ ] Config, manifests, stability, code, and analysis hashes are in the lock.
- [ ] The lock predates final output files.
- [ ] Any deviations are timestamped and disclosed.

## F. Execution

- [ ] Final run uses a clean checkout.
- [ ] Environment and hardware are recorded.
- [ ] Dependency versions are stored.
- [ ] Thread and process settings are stored.
- [ ] Every scheduled method/pair/seed unit has a status.
- [ ] Operational and algorithmic failures are distinguished.
- [ ] Incomplete runs are preserved.
- [ ] Raw result directories are never overwritten.
- [ ] Final evidence has a checksum inventory.
- [ ] Evidence is copied to at least two durable locations.

## G. Statistics

- [ ] Seeds are averaged within pair before inference.
- [ ] Pair is the observational unit.
- [ ] Primary aggregate equally weights all nine final attacks.
- [ ] Raw-EUR `C0-C3` positive-improvement orientation is unit-tested.
- [ ] Paired bootstrap uses at least 10,000 resamples.
- [ ] Primary sign-flip result is reported.
- [ ] Secondary sign-flip and Wilcoxon p-values receive Holm correction.
- [ ] Effect sizes and intervals accompany p-values.
- [ ] Failure counts and worst cases are reported.
- [ ] Non-finite and excluded values are enumerated.
- [ ] No favorable secondary result replaces a failed primary result.

## H. Tables and figures

- [ ] Every table is generated from raw evidence.
- [ ] Every figure is generated from raw evidence or original project diagrams.
- [ ] Generator commit and source hashes are stored.
- [ ] Axes, units, sample counts, and uncertainty are visible.
- [ ] Failed methods or pairs are not omitted.
- [ ] Reported article values are visually distinguished.
- [ ] No source-article figure is copied or adapted without permission.
- [ ] Color and symbols remain interpretable in grayscale.

## I. Claims

- [ ] `CLAIM_EVIDENCE_MATRIX.csv` is current.
- [ ] Every manuscript claim maps to a supported claim ID.
- [ ] Controlled, transform, and article comparisons are distinguished.
- [ ] "Reproduced" is used only for matched measured evidence.
- [ ] "Novel" is bounded by a dated prior-art search.
- [ ] "Superior" follows the preregistered success rule.
- [ ] "Secure" is not inferred from image quality or incidental attacks.
- [ ] Neutral, mixed, and negative findings are retained.
- [ ] Limitations include semi-blind access and payload differences.

## J. Reproducibility package

- [ ] Immutable source release or tag exists.
- [ ] Environment lock exists.
- [ ] Data acquisition instructions and manifests exist.
- [ ] External toolbox requirements and hashes exist.
- [ ] Raw results and analysis outputs exist.
- [ ] Protocol lock and deviation log exist.
- [ ] Generated tables and figures exist.
- [ ] Checksums verify after a fresh download.
- [ ] A clean-machine reproduction run has been attempted.
- [ ] A persistent archive identifier is assigned.

## K. Manuscript

- [ ] Title does not overclaim.
- [ ] Abstract contains design, effect, interval, failures, and boundary.
- [ ] Methods match committed code and protocol.
- [ ] Results follow the preregistered order.
- [ ] Discussion separates mechanism evidence from speculation.
- [ ] Limitations are explicit.
- [ ] Data/code availability statement is accurate.
- [ ] Funding, conflicts, and author contributions are complete.
- [ ] All citations are verified against primary sources.
- [ ] Final numerical proofread is performed against generated artifacts.

## Release decision

Record:

```text
release identifier:
source commit:
protocol-lock SHA-256:
data-manifest SHA-256:
result inventory SHA-256:
analysis identifier:
claim matrix SHA-256:
reviewer:
UTC decision time:
decision: release | hold
reason:
```
