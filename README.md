# Contourlet steganography: audited reconstruction

This repository is an independent, executable reconstruction of:

> R. Kumar, S. Singhal, and V. K. Sharma, “Efficient image steganography
> method using contourlet transform and geometric-based pixel encryption for
> enhanced security,” *Scientific Reports*, 16, 16771 (2026).
> [doi:10.1038/s41598-026-41168-0](https://doi.org/10.1038/s41598-026-41168-0)

It is **not the authors' code**, and it does not claim exact numerical
reproduction. The article omits several outcome-determining details and
contains contradictory pseudocode. This project preserves those issues as
testable assumptions instead of silently selecting convenient values.

## Current status

- AP/GP/HP preprocessing from Algorithms 1 and 4, including a strict mode that
  exposes the undefined HP branch.
- A transparent four-level, multidirectional Laplacian-pyramid backend.
- Semi-blind embedding and extraction with `alpha = 0.15`.
- Literal high-frequency and mathematically recoverable configurations.
- PSNR, global and windowed SSIM, standard and paper-equation NCC, MSE, and
  bitwise BER.
- Gaussian, salt-and-pepper, JPEG, rotation, and central-crop attacks.
- Deterministic experiment artifacts, tests, and CI.
- CSV-manifest batch runs with per-input, decoded-array, and output hashes.
- Git/config/environment provenance and explicit per-pair failure records.
- Paired bootstrap intervals, exact/Monte Carlo sign-flip tests, Wilcoxon,
  rank-biserial effects, and Holm multiplicity correction.
- A method registry that keeps future proposed algorithms out of baseline code.
- An optional MATLAB adapter for the standard `pdfbdec`/`pdfbrec` toolbox API.
- A frozen comparison protocol for adding a future proposed method.
- A separate, bit-exact `DIGITAL_A_D` path with controlled C0/C1/C2/C3
  factorial methods.
- Fixed 222,360-bit transport with Base/Detail layers, mixed/unequal
  RS protection, CRC-guarded header, deterministic scrambling and
  interleaving.
- Transform audit, coefficient-map hashing, calibration-only A stability,
  PSNR-constrained lambda search, digital-only attack profiles, and
  failure-aware evidence artifacts.
- A critically sampled orthonormal Haar engineering control that makes the
  complete digital software path executable without mislabelling it as the
  authors' Contourlet.

The built-in Python transform is explicitly named
`directional_laplacian_proxy`. It is contourlet-style, but it is not presented
as the undisclosed MATLAB LPDFB configuration used by the paper. Exact claims
must wait for the authors' filters, directional schedule, subband indices, and
datatype rules.

The new Haar profile is likewise explicit: it is an engineering control, not a
Contourlet. The existing redundant directional proxy is not suitable for
independently writing and recovering 222,360 coefficient signs at the 45 dB
constraint. Direct article-superiority claims still require an approved PDFB
backend.

## Digital A+D quick start

```bash
ctsteg audit-transform \
  --config configs/digital_ad/proxy_audit_v1.toml \
  --output results/proxy-audit.json

ctsteg digital-demo \
  --config configs/digital_ad/stage3_pilot.toml \
  --method C3_A_D \
  --attack-profile pilot \
  --output-dir results/digital-demo
```

See [the locked binary format](docs/DIGITAL_AD_FORMAT_V1.md),
[implementation and evidence contract](docs/DIGITAL_AD_IMPLEMENTATION.md), and
[stage-gate status](docs/STAGE_GATE_STATUS.md). A concise
[Persian guide](docs/DIGITAL_AD_FA.md) is also available.

The next scientific blocker has an executable, fail-closed
[MATLAB PDFB Stage-0 gate](docs/PDFB_TRANSFORM_GATE.md) and a
[Persian guide](docs/PDFB_TRANSFORM_GATE_FA.md). It audits one explicit
toolbox interpretation without enabling it or calling it author-equivalent.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
ctsteg demo --output-dir results/demo --size 128
```

Run with real images:

```bash
python scripts/download_usc_sipi.py --output-dir data/usc_sipi

ctsteg run \
  --cover data/usc_sipi/peppers.tiff \
  --secret data/usc_sipi/baboon.tiff \
  --config configs/paper_transmission.toml \
  --output-dir results/peppers_baboon
```

The downloader uses the [official USC-SIPI catalogue](https://sipi.usc.edu/database/database.php?volume=misc).
The article's label “Jet” does not identify a current catalogue entry; the
script marks F-16 as an **unverified proxy**, never as a confirmed match.

## Presets

| Configuration | What it tests | Scientific limitation |
|---|---|---|
| `paper_literal.toml` | Finest directional bands only; no low-pass | Follows “highest frequency” wording, but cannot reconstruct a full secret |
| `paper_recoverable_float.toml` | All details plus low-pass; no stego quantization | Reversible numerical control; not a transmitted 8-bit image |
| `paper_transmission.toml` | All coefficients followed by 8-bit quantization | Coherent transmission test; broader embedding than the wording states |

The output directory contains source, encrypted, stego, difference, and
recovered PNGs; `metrics.json`; an overview panel; per-attack recovered images;
and `attack_metrics.csv`.

## Batch benchmark and paired comparison

This original batch path remains the route for methods that share P0's
512×512 analogue-secret contract:

```bash
python scripts/download_usc_sipi.py --output-dir data/usc_sipi

ctsteg benchmark \
  --manifest examples/pairs.example.csv \
  --config configs/paper_transmission.toml \
  --method paper_baseline \
  --output-dir results/baseline-v1 \
  --save-artifacts

# After a separately registered method named "proposed" exists:
ctsteg benchmark \
  --manifest examples/pairs.example.csv \
  --config configs/paper_transmission.toml \
  --method proposed \
  --output-dir results/proposed-v1 \
  --save-artifacts

ctsteg compare \
  --baseline results/baseline-v1/results_long.csv \
  --proposed results/proposed-v1/results_long.csv \
  --output-dir results/comparison-v1
```

The comparator refuses mismatched paired units and detected manifest,
configuration, attack-option, or input-hash differences by default. Positive
reported improvement always means the candidate is better after respecting
whether a metric is minimized or maximized. See
[the benchmark contract](docs/BENCHMARKING.md) and the
[Persian guide](docs/BENCHMARKING_FA.md).

## Why exact reproduction is not yet supportable

The most consequential blockers are:

1. Algorithm 1 iterates over `0..255` rows and columns, while all experiments
   are stated as 512×512.
2. Within the 8-bit domain, `L1 = 1,4,7,...` and
   `L2 = 511,508,...,1` select the same residue class. The `N/4 + 193` AP branch
   is therefore unreachable after the outer `not in L1` condition.
3. `CODE_HP` specifies an output only for values in `0..32`; half of ordinary
   image positions can therefore have no defined output.
4. The CT filter names, boundary mode, directional-level vector, and exact
   embedded subband are absent.
5. The paper calls the CT subsampled but counts four full arrays at every
   scale, which is inconsistent with a critically sampled transform.
6. Quantization and clipping rules are omitted even though premature 8-bit
   conversion destroys reversibility.
7. Attack definitions and tables conflict for Gaussian variance and crop
   percentage.

See [the full reproducibility audit](docs/REPRODUCIBILITY_AUDIT.md).

## Validating the digital A+D method

The implemented digital path keeps P0 unchanged and exposes C0/C1/C2/C3 as a
prospective 2×2 factorial experiment. Its 128×128 digital-secret contract is
not silently forced through the older P0 benchmark interface. Use
`digital-benchmark` and `digital-factorial` for the controlled digital
comparisons, and report paired per-image results, corrected tests, effects,
failures, ablations, and negative results.

The complete plan is in [NOVELTY_PROTOCOL.md](docs/NOVELTY_PROTOCOL.md);
the executable comparison workflow is in
[BENCHMARKING.md](docs/BENCHMARKING.md), and the staged Persian roadmap is in
[ROADMAP_FA.md](docs/ROADMAP_FA.md).
Improved averages are empirical evidence, not by themselves proof of technical
novelty; novelty also requires a defensible prior-art analysis and a precise
statement of the new mechanism.

## Security warning

The AP/GP/HP mapping is deterministic, keyless, and visibly structured. It is
not cryptographic encryption under a modern threat model. This repository
retains the paper's terminology only for traceability and must not be used to
protect sensitive data.

## Repository layout

```text
configs/          frozen interpretations of underspecified choices
docs/             audit, reported targets, and future comparison protocol
examples/         pairing-manifest examples (no copyrighted images)
scripts/          USC-SIPI acquisition helper
src/ctsteg/       methods, benchmark, statistics, pipeline, attacks, and CLI
tests/            deterministic unit and integration tests
matlab/           optional adapter for the standard Contourlet Toolbox
```

## Licensing and source material

The code in this repository is MIT licensed. The article PDF, its figures, and
USC-SIPI images are not redistributed. They remain subject to their own terms.
The method is cited and linked rather than copying the paper into the project.
