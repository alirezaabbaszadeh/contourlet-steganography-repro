# Scientific Reports submission readiness

Status: manuscript-level scientific and visual revision completed; identity and private-capsule items remain author-controlled.

## Completed

- Human-edited title, abstract, introduction, discussion, and conclusion.
- Four controlled C0--C3 variants described under fixed payload and realised PSNR.
- Architecture, factorial-design, Base-protection, and channel-outcome figures.
- Novelty table framed as prior contribution versus remaining gap.
- Main execution table and engineering detail moved to Supplementary Information.
- Explicit claim boundary: code-level Base advantage without attacked-channel end-to-end advantage.
- Generative-AI disclosure, research-ethics statement, data/code statements, and competing-interest statement.
- Deterministic scripts for private-capsule telemetry and representative image panels.

## Must be confirmed by the author before submission

- Institutional affiliation and corresponding-author email.
- ORCID for the corresponding author.
- Funding statement and grant identifiers, or explicit confirmation of no external funding.
- Final CRediT contribution statement.
- Acknowledgements, if any.
- Release tag or archived DOI for the exact submitted manuscript snapshot.

## Private-capsule actions

Run the diagnostic exporter against the locked 88-row report:

```bash
python scripts/build_manuscript_diagnostics.py \
  --input /path/to/private-capsule/final-report.parquet \
  --output-dir results/manuscript-diagnostics \
  --expected-run-id f7acf6d9d31dd66cddf1
```

Create the visual panel from the first pair in the locked manifest, chosen before inspecting appearance:

```bash
python scripts/build_representative_panel.py \
  --pair-id PAIR_ID_FROM_LOCKED_MANIFEST \
  --cover /path/to/cover.png \
  --secret /path/to/secret.png \
  --stego-c0 /path/to/C0-stego.png \
  --stego-c3 /path/to/C3-stego.png \
  --clean-recovered /path/to/clean-recovered.png \
  --output figures/representative-pair.png
```

Only insert diagnostic plots if the exporter records the expected run ID and archive hash. Label them exploratory and do not alter the locked primary EUR conclusion.

## Final preflight

- Compile the manuscript twice and Supplementary Information once.
- Render every PDF page and inspect figures, tables, citations, and long identifiers.
- Confirm that every cited novelty gap is supported by the cited full text.
- Replace all bracketed identity/funding placeholders.
- Archive the exact source tree and record its release tag or DOI.
