# Article and evidence freeze

Status: **FINAL-5J scientific execution, analysis, and numerical evidence are frozen; manuscript finalisation only**.

The submitted article is bound to the following evidence contract:

- Protocol: `FINAL-5J-v1`.
- Five internal methods: C0, C1, C2, C3_NP, and C3.
- Two harmonized external baselines: B1 and B2.
- Version-2 layer-integrity payload format with Base/Detail semantics for the internal methods.
- Full internal protected stream size: 222,360 bits at the 100% operating point.
- Frozen transform profile: `octave_pdfb_9_7_pkva_nlev_2222_p3p4_range_v2`.
- Main study: 50 preregistered cover--secret pairs, 7 methods, 350 embeddings, and 7,700 channel evaluations.
- Preregistered payload sweep: 10-pair subset, 90 incremental embeddings, and 360 evaluations.
- Preregistered PSNR sweep: 10-pair subset, 90 incremental embeddings, and 360 evaluations.
- Frozen totals: 530 embeddings, 8,420 evaluations, and 8,950 planned tasks.
- Main channel matrix: clean; JPEG quality 90/70/50; Gaussian variance 5/10/15 with three locked realizations per severity; salt-and-pepper density 0.01/0.03/0.05 with three locked realizations per severity.
- Production worker count: 20.
- Plan ID: `ec0be4f6b76c8a63399be3385ae18f2e3931290becb8fe80c58845025cbb5e30`.
- Run ID: `5j-ec0be4f6b76c8a63399b`.
- Scientific production source commit: `2891c2a1ad1ce725038ed0a7524adf6c23abcfa0`.
- Final analysis source commit: `45ce51220d14ab10d480c734fe0a22b5a860c4bc`.
- Immutable result snapshot branch: `results/final-5j-20260812`.
- Immutable result snapshot tag: `FINAL-5J-RESULTS-20260812`.
- Reviewable result package: `docs/5j/final-run-20260812/`.

The final analysis contains all 8,420 raw evaluation rows, zero missing rows, zero invalid rows, `partial_analysis=false`, and 10,000 pair-cluster bootstrap repetitions. Operational failures were zero. Scientific prerequisite and recovery failures remain part of the frozen evidence and must not be removed, repaired post hoc, or converted to numerical zeros.

No further algorithm, configuration, calibration, transform, test-matrix, embedding, attack, baseline, worker-selection, or numerical-result change belongs in manuscript finalisation for this article.

Permitted work is limited to:

- human editing for clarity, cohesion, terminology, and scientific precision without changing the frozen claims or numbers;
- deterministic regeneration of manuscript tables/figures from the frozen reporting snapshot;
- caption, typography, page-layout, citation, and reference refinement;
- journal-specific formatting and submission packaging;
- author identity, affiliation, correspondence, ORCID, funding, CRediT, acknowledgement, and disclosure metadata;
- PDF compilation and page-by-page visual QA;
- release tagging or DOI archival of the exact source tree used for submission.

Any future algorithmic or experimental extension must use a new protocol version, run identity, evidence archive, and manuscript claim set. It must not overwrite, reinterpret, or silently replace the frozen FINAL-5J evidence used by this article.
