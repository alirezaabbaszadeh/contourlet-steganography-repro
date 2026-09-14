# Final manuscript figures

The algorithm, transform profile, payload, channel matrix, and numerical results are frozen. This directory is for publication assets only.

## Representative image panel

Generate the panel from the first pair in the locked manifest, selected before visual inspection:

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

The command creates:

- `figures/representative-pair.png` for inspection and submission systems that request raster artwork;
- `figures/representative-pair.pdf` for automatic inclusion in the LaTeX manuscript;
- `figures/representative-pair.json` with source hashes, output hashes, pair identity, PSNR values, and exact-recovery status.

`paper/04_results.tex` includes the PDF automatically when it is present. The manuscript still compiles when the private image panel has not yet been generated.

## Publication boundary

- Do not regenerate embeddings, attacks, calibration, or evaluation rows.
- Do not change the selected pair after viewing the panel.
- Do not manually edit image pixels or printed metrics.
- Do not commit rights-limited source images.
- Commit the derived panel only when redistribution rights permit it; otherwise add it to the private submission package and build the PDF in that controlled environment.
