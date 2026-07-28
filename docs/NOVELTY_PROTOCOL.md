# Protocol for adding and substantiating a proposed method

## 1. Separate two claims

The future paper must not collapse these distinct questions:

1. **Technical novelty:** is the proposed mechanism absent from the relevant
   prior art, and is the difference technically meaningful rather than a
   renamed parameter or routine combination?
2. **Empirical superiority:** under a fixed and fair protocol, does the method
   improve predefined outcomes by a meaningful amount?

Higher PSNR or SSIM cannot, by itself, prove novelty. A novelty claim requires a
dated, documented search and a claim-by-claim comparison against the closest
methods. Empirical evidence requires paired experiments and uncertainty
estimates.

## 2. Freeze the baseline before development

- Tag the audited baseline and record its commit SHA.
- Do not edit baseline source to accommodate the proposed method.
- Keep each ambiguity resolution in a named configuration.
- Store environment, dependency versions, seed, input hashes, configuration,
  elapsed time, and output hashes with every run.
- Treat the article's printed metrics as external targets, never as values to
  insert into generated result files.

The executable manifest, provenance, and paired-analysis contract is now
implemented and documented in [`BENCHMARKING.md`](BENCHMARKING.md). Use that
path for every comparative run; do not assemble article tables by hand.

## 3. Define the proposed contribution prospectively

Before inspecting test results, write:

- the exact new component and where it enters the pipeline;
- a threat model and attacker knowledge;
- a primary hypothesis and one primary metric;
- expected failure modes;
- fixed hyperparameter search space and tuning split;
- stopping and exclusion rules.

Add the method behind the same transform/pipeline interface. A configuration
must select `baseline` or `proposed` without changing data or evaluation code.

## 4. Fair comparison controls

Hold constant:

- grayscale/color conversion and resize kernel;
- cover-secret pairs and payload;
- `alpha`, or compare on a matched-distortion/matched-payload curve;
- transform levels and coefficient budget unless they are the declared
  contribution;
- file format and quantization boundary;
- attack realization and random seed;
- metric implementation;
- hardware, worker count, warm-up, and timing boundary.

If the proposed method changes payload, compare rate-distortion-robustness
frontiers rather than a single hand-picked operating point.

## 5. Dataset and evaluation design

- Use the paper's identifiable USC-SIPI images for traceability.
- Add a substantially larger, independently sourced test set; five images
  cannot support broad claims.
- Split development/tuning data from the final locked test set.
- Hash each input and publish the pairing manifest.
- Do not redistribute images whose rights do not permit it; provide acquisition
  scripts and identifiers.
- Run multiple seeds wherever the method or attack is stochastic.

## 6. Predefined outcomes

Recommended primary outcomes:

- imperceptibility at fixed payload: PSNR and local-window SSIM;
- recovery: bitwise BER and standard normalized correlation;
- robustness: BER after each predefined attack intensity;
- efficiency: wall-clock time, peak memory, and coefficient count.

Security claims need direct tests appropriate to the threat model. Histogram
similarity and visual inspection do not establish cryptographic security.
For a key-based design, evaluate key space, key sensitivity, known-cover and
chosen-cover behavior, leakage, and failure under incorrect keys. Avoid calling
a deterministic keyless mapping “encryption.”

## 7. Statistical analysis

Use image pairs as the paired observational unit.

1. Publish every per-image/per-seed result.
2. Report mean, median, standard deviation, and 95% paired bootstrap confidence
   intervals (at least 10,000 resamples).
3. Test the preregistered primary difference with a paired permutation test or
   Wilcoxon signed-rank test when distributional assumptions are unsuitable.
4. Report an effect size and its interval, not only a p-value.
5. Correct secondary-family multiplicity, for example with Holm's procedure.
6. Include failure counts and worst-case results.
7. Do not infer practical superiority from a statistically detectable but
   negligible difference.

## 8. Required ablations

At minimum compare:

- paper baseline;
- baseline plus only the proposed component;
- proposed method with each new component removed;
- matched-complexity control;
- matched-payload and matched-PSNR controls;
- float control versus actual 8-bit transmission;
- with and without attack registration, if registration is part of the method.

## 9. Robustness matrix

Use identical attacked stego images for paired comparison:

- Gaussian variance: 5, 10, 15;
- salt-and-pepper density: 0.01, 0.03, 0.05;
- JPEG quality: 90, 70, 50;
- rotation: 15°, 30°, 45°;
- central keep-fraction: 0.90, 0.75, 0.60.

Also add realistic attacks justified by the intended application. Clearly
separate attacks chosen before testing from exploratory attacks added later.

## 10. Evidence package for the future article

The submission package should contain:

- frozen baseline and proposed-method SHAs;
- machine-readable configurations and environment lock;
- input manifest and hashes;
- raw results and analysis script;
- generated tables/figures (never hand-copied values);
- ablations, uncertainty intervals, and corrected tests;
- threat-model limitations and negative results;
- a closest-prior-art claim chart;
- an explicit statement that this repository is an independent reconstruction
  unless author code is later obtained.

This structure supports a defensible claim of evidence. It deliberately avoids
the stronger word “proof” unless the claim is a formal theorem with stated
assumptions and a valid mathematical proof.

The project-specific estimands, primary success rule, sample-size gate,
failure policy, and execution order are now frozen prospectively in
[`RESEARCH_PROTOCOL.md`](RESEARCH_PROTOCOL.md). Claim wording must also pass
[`CLAIMS_AND_EVIDENCE.md`](CLAIMS_AND_EVIDENCE.md) and its machine-readable
matrix before entering the manuscript.
