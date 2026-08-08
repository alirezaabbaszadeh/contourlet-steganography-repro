# Scientific Reports submission readiness

Status: **algorithm, transform, experiment, and numerical evidence frozen; manuscript finalisation only**.

See `docs/ARTICLE_FREEZE.md` for the binding boundary. No further algorithm, configuration, test-matrix, embedding, attack, or result changes are required for this article.

## Completed

- Positive, human-edited title, abstract, introduction, system narrative, methods, results, discussion, and conclusion.
- Cohesive story from perceptual Base/Detail importance through hierarchical protection, transform-aware placement, clean validity, and the measured recovery boundary.
- Four controlled C0--C3 configurations described under the same payload and realised PSNR.
- Architecture, C0--C3 mechanism, Base-protection, and channel-boundary figures.
- Novelty table framed around the integrated contribution rather than isolated components.
- Verified emphasis on the 51.2% Base correction-budget increase and 60.2% protected-body share.
- Self-describing validity, independent PDFB coordinates, and reproducible execution presented as positive system contributions.
- Main execution detail moved to Supplementary Information.
- Generative-AI disclosure, research-ethics statement, data/code statements, and competing-interest statement.
- Publication-ready deterministic representative-panel generator.
- Conditional manuscript integration for `figures/representative-pair.pdf`.
- Development test workflow retired and replaced by a manuscript-only PDF build.

## Remaining publication assets

### 1. Generate the representative image panel

Use the first pair in the locked manifest and the frozen private artifacts:

```bash
python scripts/build_representative_panel.py \
  --pair-id PAIR_ID_FROM_LOCKED_MANIFEST \
  --cover /path/to/private-capsule/cover.png \
  --secret /path/to/private-capsule/secret.png \
  --stego-c0 /path/to/private-capsule/C0-stego.png \
  --stego-c3 /path/to/private-capsule/C3-stego.png \
  --clean-recovered /path/to/private-capsule/clean-recovered.png \
  --output figures/representative-pair.png
```

The generator creates PNG, PDF, and JSON provenance outputs. The PDF is included automatically by `paper/04_results.tex`.

Do not commit rights-limited source images. Commit the derived panel only when redistribution rights permit it; otherwise build the submitted manuscript in the controlled private environment.

### 2. Inspect the publication PDFs

Run the `manuscript` GitHub workflow or trigger it manually. Inspect the uploaded `manuscript-pdfs` artifact page by page for:

- figure scale and readability;
- table width and wrapping;
- citation resolution;
- long hashes and identifiers;
- page breaks and float placement;
- consistency between the main article and Supplementary Information.

### 3. Supply author-controlled metadata

- institutional affiliation;
- corresponding-author email;
- ORCID;
- funding statement and grant identifiers, or explicit no-funding statement;
- final CRediT contribution statement;
- acknowledgements, if any.

### 4. Freeze the submission snapshot

Create a release tag or DOI archive for the exact source tree used to produce the submitted PDFs. Record that identifier in the Code Availability statement.

## Submission-complete condition

The article is ready for submission when the representative panel has been handled according to image rights, the publication PDFs have been visually inspected, author metadata has been supplied, and the exact source snapshot has been archived.
