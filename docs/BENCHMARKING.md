# Reproducible benchmark and paired comparison

## Scope

The benchmark harness separates three layers:

1. a registered embedding/extraction method;
2. fixed data, attacks, metrics, and provenance capture;
3. paired statistical analysis.

Only `paper_baseline` is registered at present. No proposed algorithm is
invented by this repository. When its mechanism is specified, it must implement
the same method interface and produce a separate result directory.

## Pair manifest

The manifest is UTF-8 CSV. Required columns are:

| Column | Meaning |
|---|---|
| `pair_id` | Filesystem-safe identifier for the cover/secret pair |
| `cover` | Cover image path, relative to the manifest unless absolute |
| `secret` | Secret image path, relative to the manifest unless absolute |

Optional columns:

| Column | Meaning |
|---|---|
| `split` | Locked split label; defaults to `test` |
| `seed` | Non-negative run seed; defaults to the TOML configuration seed |
| any other column | Preserved as provenance metadata |

The pair identifier and seed jointly identify one execution unit, and duplicate
execution units are rejected. Statistical inference still uses the image pair
as the observational unit: repeated seeds are averaged within each `pair_id`
before resampling or testing, preventing pseudoreplication. See
[`examples/pairs.example.csv`](../examples/pairs.example.csv). The example
pairings are operational examples, not a claim about the exact pairing used by
the article.

## Baseline benchmark

Acquire the traceability images, then run:

```bash
python scripts/download_usc_sipi.py --output-dir data/usc_sipi

ctsteg benchmark \
  --manifest examples/pairs.example.csv \
  --config configs/paper_transmission.toml \
  --method paper_baseline \
  --output-dir results/baseline-v1 \
  --save-artifacts
```

An output directory must be absent or empty. This is intentional: stale
artifacts from a prior configuration must not be mixed with a new run.

The output contract is:

| File | Contents |
|---|---|
| `results_long.csv` | One metric per method/pair/seed/scope/attack |
| `summary.csv` | Descriptive aggregates with explicit non-finite counts |
| `benchmark.json` | Per-unit input/output hashes, timings, failures, metadata |
| `provenance.json` | Data/config/evaluator hashes, Git state, UTC time, environment |
| `artifacts/` | Optional stego, recovered, diagnostics, and attacked recoveries |

Array hashes include shape, explicit little-endian float64 dtype, and canonical
row-major bytes. File hashes refer to the original input files before resize or
grayscale conversion; decoded-array hashes capture the actual benchmark input.

The default attack matrix is shared with the audited single-run pipeline:
Gaussian variance 5/10/15, salt-and-pepper density 0.01/0.03/0.05, JPEG quality
90/70/50, rotation 15/30/45 degrees, and central keep-fraction 0.90/0.75/0.60.
Stochastic attacks reuse the same seed and therefore the same random
realization contract for each paired method run.

## Add the proposed method

Create a separate implementation, for example
`src/ctsteg/proposed.py`, with this interface:

```python
class ProposedMethod:
    name = "proposed"
    version = "1"

    def embed(self, cover, secret, config):
        # Return ctsteg.methods.MethodEmbedding.
        ...

    def extract(self, stego, original_cover, config, *, context=None):
        # Return ctsteg.methods.MethodExtraction.
        ...
```

Register its zero-argument factory with
`ctsteg.methods.register_method("proposed", ProposedMethod)`. For a built-in
repository method, import and register it in `methods.py` so a fresh `ctsteg`
process can resolve it. Keys or other ephemeral extraction state belong in
`MethodEmbedding.extraction_context`; it is passed to clean and attacked
extraction but is never serialized.

Run the candidate with exactly the same manifest and shared TOML configuration:

```bash
ctsteg benchmark \
  --manifest examples/pairs.example.csv \
  --config configs/paper_transmission.toml \
  --method proposed \
  --output-dir results/proposed-v1 \
  --save-artifacts
```

Method-specific parameters must be explicit in the method version and its
metadata until a dedicated, validated candidate configuration schema is added.
They must never be tuned on the locked test split.

The harness verifies that a method returns the exact decoded cover and secret
references it received, then computes all metrics against protected originals.
A candidate therefore cannot improve its score by replacing or preprocessing
the reference arrays. The extraction context must be treated as read-only
across clean and attacked calls.

## Paired analysis

```bash
ctsteg compare \
  --baseline results/baseline-v1/results_long.csv \
  --proposed results/proposed-v1/results_long.csv \
  --output-dir results/comparison-v1 \
  --bootstrap-resamples 10000 \
  --permutation-resamples 10000 \
  --seed 2026
```

The comparator:

- aligns runs by pair identifier and seed within each metric group;
- averages repeated finite seeds within each image pair, then treats the image
  pair as the unit for bootstrap intervals and tests;
- refuses incomplete paired sets by default;
- refuses mismatched manifest, shared configuration, attack option, or recorded
  input hashes when both provenance packages are present;
- refuses changed benchmark, manifest, image-I/O, metric, or attack source
  hashes between methods;
- orients every effect so a positive value means the candidate is better;
- reports a paired-bootstrap 95% interval for mean improvement;
- uses an exact two-sided sign-flip test for at most 16 pairs and Monte Carlo
  sign flips otherwise;
- reports Wilcoxon signed-rank and matched-pairs rank-biserial effect size;
- applies Holm correction across the full comparison family;
- excludes an image pair if any of its aligned seed values is non-finite, while
  reporting both pair-level and seed-level counts.

Outputs are `comparison.csv`, `comparison.json`, and `comparison.md`.
`comparison.json` also records hashes of both raw result files, the statistical
analysis source, environment, Git state, timestamps, and a stable analysis ID.
`--allow-incomplete-pairs` and `--allow-provenance-mismatch` are explicit
diagnostic overrides. A comparison produced with either override must not be
presented as a controlled head-to-head result without explaining the mismatch.

Timing is recorded because efficiency matters, but inferential timing claims
require controlled hardware, fixed thread counts, warm-up, and repeated
process-level measurements. A single timing row is diagnostic, not a reliable
performance conclusion.

## What the analysis can and cannot establish

The generated report measures empirical paired differences. It can support a
predeclared superiority claim when the dataset, payload, operating point,
family of tests, and practical threshold are defensible. It cannot establish
technical novelty, cryptographic security, or a universal advantage. Those
claims require the separate prior-art, threat-model, ablation, and failure
analysis defined in [`NOVELTY_PROTOCOL.md`](NOVELTY_PROTOCOL.md).
