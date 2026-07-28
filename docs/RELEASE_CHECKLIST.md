# Lean research release checklist

## Code and transform

- [ ] Exact research commit is recorded and clean.
- [ ] All tests pass.
- [ ] All six protected P0 files match frozen hashes.
- [ ] MATLAB PDFB raw evidence is archived.
- [ ] Independent PDFB validation passes.
- [ ] Human review records toolbox paths, hashes, band shapes, capacity,
      reconstruction, and probes.
- [ ] Transform fingerprint matches every DIGITAL_A_D artifact.

## Fixed numerical contract

- [ ] Cover is 512x512 grayscale uint8.
- [ ] Secret is 128x128 grayscale uint8.
- [ ] Protected payload is exactly 222,360 bits for C0-C3.
- [ ] Stego PSNR is `45.0 ± 0.1 dB`.
- [ ] Rounding, clipping, and extraction rules are identical across methods.
- [ ] Clean algorithmic failures were not hidden by changing payload or PSNR.

## Data

- [ ] Baboon, Boat, Peppers, and House source identities are recorded.
- [ ] Four secret assignments were frozen before outcomes.
- [ ] File and decoded-array hashes are present.
- [ ] Rights decisions and acquisition instructions are present.
- [ ] Core manifest contains exactly four unique pairs.
- [ ] Calibration uses at most two disjoint non-reporting pairs.
- [ ] No pair is repeated to create a seed sweep.

## Run budget

- [ ] Runtime Gate passed on the target persistent server disk.
- [ ] Gate used a real `SIGKILL` and reused unchanged cache objects.
- [ ] Runtime Gate fingerprint matches the executed runner.
- [ ] Automatic worker count and memory reserve are recorded.
- [ ] Core plan contains exactly 64 rows.
- [ ] Exactly 16 core embeddings are planned and saved.
- [ ] Core channels are only Clean, JPEG 70, Gaussian 10, and S&P 0.03.
- [ ] Low-severity Q=90, variance=5, and density=0.01 are not scheduled.
- [ ] Each optional hard family has a recorded trigger decision.
- [ ] A triggered hard family adds exactly eight C0/C3 rows.
- [ ] Conditional total is at most 24.
- [ ] Overall result count is at most 88.
- [ ] No scientific repeated-seed factor exists.

## Results

- [ ] Every complete cache object passes its deep SHA-256 inventory.
- [ ] No completed embedding or evaluation was recomputed on resume.
- [ ] Failed attempts, stale locks, and quarantined objects are retained.
- [ ] Every scheduled row has success, failure, or blocked status.
- [ ] Operational reruns retain the failed artifact and reuse the same
      deterministic realization.
- [ ] Algorithmic failures remain in the results.
- [ ] Raw C0-C3 rows are immutable.
- [ ] Per-case A, D, A-by-D, and C0-C3 contrasts are generated.
- [ ] Mean, median, range, and direction count are generated.
- [ ] PSNR, SSIM, BER, EUR, CRC, runtime, and memory are retained.
- [ ] No population-level p-value, achieved-power, or confidence claim is made
      from four cases.

## Claims

- [ ] Every conclusion names or clearly bounds the four traceability cases.
- [ ] Tested channel conditions are explicit.
- [ ] P0, engineering controls, explicit PDFB, and DIGITAL_A_D are not mixed.
- [ ] Author-equivalent reproduction is not claimed without missing parameters.
- [ ] Universal superiority is not claimed.
- [ ] Untested geometric robustness is not claimed.
- [ ] Cryptographic security is not claimed.
- [ ] Neutral or negative evidence was not expanded with unplanned runs.
- [ ] `CLAIM_EVIDENCE_MATRIX.csv` matches the final artifacts.

## Archive

- [ ] CSV, JSON, JSONL, and Parquet evaluation tables are archived.
- [ ] Resource records and full stdout/stderr logs are archived.
- [ ] Four-row manifest, inventories, configs, and hashes are archived.
- [ ] The 16 stego artifacts are archived.
- [ ] All 64-88 raw result rows are archived.
- [ ] Conditional trigger records are archived, including `not_triggered`.
- [ ] Tables and figures are generated from raw rows.
- [ ] Checksum inventory is archived.
- [ ] The downloadable archive verifies against `checksums.sha256`.
- [ ] README contains exact regeneration instructions.
