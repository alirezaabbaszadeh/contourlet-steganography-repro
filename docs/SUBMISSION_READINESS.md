# Scientific Reports submission readiness

Status: **FINAL-5J evidence frozen; manuscript technically complete pending author-controlled metadata, final PDF QA, and submission snapshot archival**.

See `docs/ARTICLE_FREEZE.md` for the binding scientific boundary. The manuscript branch is `paper/final-5j`; the immutable numerical result base is tag `FINAL-5J-RESULTS-20260812` and branch `results/final-5j-20260812`.

## Completed

- Manuscript rewritten against the verified FINAL-5J result snapshot rather than the earlier traceability study.
- Five internal methods (C0, C1, C2, C3_NP, C3) and two harmonized external baselines (B1, B2) described under one frozen comparison contract.
- Main study totals fixed at 50 preregistered pairs, 350 main embeddings, and 7,700 main evaluations.
- Two preregistered 10-pair sweeps add 180 embeddings and 720 evaluations, giving 530 embeddings and 8,420 evaluations overall.
- Zero operational failures; zero missing and zero invalid analysis rows; `partial_analysis=false`.
- Results, tables, figures, and manuscript macros generated from the tracked FINAL-5J reporting package in `docs/5j/final-run-20260812/`.
- Main scientific interpretation aligned with the frozen analysis: C3 does not improve complete recovery over C0; C3 has a small lower raw BER; C3 and C3_NP show no detectable placement benefit on complete recovery or BER; B1 retains stronger partial recovery; C3 has higher complete recovery than B2 under the frozen baseline contract.
- Payload and PSNR sweep findings included in the manuscript and Supplementary Information.
- Terminology standardized to `external baselines`; obsolete pilot-specific narrative removed from the submission manuscript.
- Main manuscript and Supplementary Information have dedicated LaTeX entry points: `manuscript.tex` and `supplementary_information.tex`.
- GitHub workflow `.github/workflows/manuscript.yml` builds both PDFs and uploads the publication artifact.
- Immutable result lineage records the production source commit `2891c2a1...` and final analysis source commit `45ce512...`.
- Scientific Reports submission requirements were re-audited against the official journal guidance on 2026-08-13; see `docs/SCIENTIFIC_REPORTS_SUBMISSION_AUDIT_20260813.md`.
- Current journal limits are satisfied: 9-word title, 142-word expanded abstract, 6 keywords, approximately 3,446 main-text words under the journal exclusion rule, and 8 main-article display items (4 figures + 4 tables; at the journal limit).
- Substantive LLM assistance is disclosed in Methods, with the author retaining responsibility for the scientific content.
- A FINAL-5J-specific Scientific Reports cover-letter draft is prepared in `Cover_Letter_Nature_Portfolio.md` with only author-controlled metadata/reviewer fields left unresolved.

## Remaining submission inputs

### 1. Author-controlled metadata

Supply and confirm:

- institutional affiliation;
- corresponding-author email;
- ORCID, if used for submission;
- funding statement and grant identifiers, or an explicit no-external-funding statement;
- final CRediT contribution statement;
- acknowledgements, if any.

These fields must not be guessed from repository history or public profiles.

### 2. Journal-specific finishing pass

Scientific Reports is the active target and its current submission rules have been audited. Remaining journal-level work is limited to inserting the author-controlled metadata, confirming the declarations and cover-letter fields, checking the final Nature-style reference presentation, and rebuilding the exact submission PDFs. Do not alter the frozen scientific matrix or numerical evidence to fit editorial preferences.

### 3. Publication PDF QA

Run the `manuscript` GitHub workflow (or compile locally from the same source tree) and inspect both PDFs page by page for:

- figure scale and readability;
- table width and wrapping;
- citation and cross-reference resolution;
- long hashes/identifiers and line breaks;
- blank pages, clipping, overfull/underfull boxes, and float placement;
- consistency between the main article and Supplementary Information.

Any typography-only fix should be committed to `paper/final-5j` and the PDFs rebuilt from the new commit.

### 4. Freeze the exact submission source

After metadata and journal formatting are complete:

1. confirm local `paper/final-5j` equals GitHub and the working tree is clean;
2. build and visually inspect the final manuscript and Supplementary PDFs;
3. record the exact commit SHA and PDF SHA256 values;
4. create a submission tag/release (separate from the immutable results tag);
5. archive the exact submission source in the selected DOI repository if required by the journal;
6. record the final archival identifier in the Code Availability statement when appropriate.

## Submission-complete condition

The article is submission-complete when author metadata is supplied, the target-journal formatting pass is complete, both PDFs are rebuilt and visually inspected from one clean commit, and that exact source snapshot is tagged/archived. No new experiment is required for manuscript finalisation under the current freeze.
