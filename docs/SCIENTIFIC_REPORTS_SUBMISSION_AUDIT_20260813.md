# Scientific Reports submission audit — 2026-08-13

Target: **Scientific Reports — Article**

Authoritative sources checked on 2026-08-13:

- Submission guidelines: https://www.nature.com/srep/author-instructions/submission-guidelines
- AI policy: https://www.nature.com/srep/journal-policies/ai
- Editorial and publishing policies: https://www.nature.com/srep/journal-policies/editorial-policies
- Ready-to-submit checklist: https://www.nature.com/srep/author-instructions/ready-to-submit

## Current compliance snapshot

| Requirement | Journal guidance | Current manuscript | Status |
|---|---|---|---|
| Title length | no more than 20 words | 9 words | PASS |
| Abstract | no more than 200 words; unstructured; no references | 142 words after expanding generated values; unstructured; no references | PASS |
| Keywords | up to 6 | 6 | PASS |
| Main text | recommended no more than 4,500 words excluding Abstract, Methods, References and figure legends | approximately 3,446 words by repository audit | PASS |
| Display items | maximum 8 figures/tables | 4 figures + 4 tables = 8 | PASS |
| Data Availability | mandatory, before References | present before References | PASS |
| Competing Interests | mandatory | present | PASS |
| Author Contribution Statement | mandatory | present, pending author confirmation | PENDING AUTHOR CONFIRMATION |
| Corresponding author marker | identify corresponding author with an asterisk | asterisk added; affiliation/email remain placeholders | PENDING METADATA |
| LLM use | substantive LLM use should be documented in Methods | documented in Methods; human responsibility stated | PASS |
| Supplementary Information | separate file; title and author list on first page | separate `supplementary_information.tex`; title and author present | PASS |
| Cover letter | required | FINAL-5J draft prepared | PENDING METADATA / OPTIONAL REVIEWER DETAILS |
| LaTeX compilation | complete TeX should compile without errors or warnings | GitHub manuscript workflow performs two-pass builds; final CI must be checked after each submission edit | GATED BY CI |

## Author-controlled items still required

- institutional affiliation;
- corresponding-author email;
- ORCID if used;
- funding statement / grant numbers or explicit no-external-funding statement;
- confirmation of the CRediT-style author contribution statement;
- acknowledgements if any;
- cover-letter reviewer suggestions/exclusions if desired;
- confirmation of whether there has been prior discussion with a Scientific Reports Editorial Board Member.

## Submission packaging rule

Do not use tracked historical root PDFs. The authoritative publication PDFs are generated from the exact `paper/final-5j` source commit by `.github/workflows/manuscript.yml` (or from the same clean source tree in the controlled local build). Record the final source commit and PDF SHA256 values before creating the submission tag/release.

No new experiment, parameter tuning, or numerical-result change is required or permitted under the current article freeze.
