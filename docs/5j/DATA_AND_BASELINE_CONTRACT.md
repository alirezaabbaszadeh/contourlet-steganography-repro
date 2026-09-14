# FINAL-5J-v1 Data and Baseline Contract

Status: implementation baseline  
Protocol: `FINAL-5J-v1`

## 1. Data splits

The study uses four named, machine-readable splits:

1. `calibration` — transform-stability estimation only;
2. `dry_run` — engineering verification only;
3. `main` — exactly 50 preregistered scientific pairs;
4. `sweep` — exactly 10 preregistered pairs that are an exact-byte subset of `main`.

Calibration and dry-run pairs must be disjoint from the main study by pair ID and image SHA-256. The sweep is not a new population; it is a frozen subset of main.

## 2. Candidate catalog and deterministic freeze

The author/operator supplies at least 54 actual, preprocessed, rights-documented candidate pairs using:

```text
data-manifests/5j/candidate_pairs.template.csv
```

The repository must not invent image sources, licenses, permissions, or rights status. The freeze command validates all candidate files and selects pairs without using algorithmic outcomes:

```bash
python scripts/5j/freeze_data_manifests.py \
  --catalog /data/final-5j-candidate-pairs.csv \
  --output-dir data-manifests/5j \
  --report data-manifests/5j/data_freeze_report.json
```

Selection contract:

- compute a protocol/version-domain SHA-256 score from pair ID and cover/secret hashes;
- first two ordered pairs become calibration;
- next two become engineering dry run;
- next 50 become main;
- 10 main pairs with the lowest independent sweep-domain score become sweep;
- all remaining candidates are recorded as excluded, not silently discarded.

## 3. Required pair metadata

Every row records:

- pair ID and split;
- cover and secret paths;
- cover and secret SHA-256;
- source and license for each image;
- rights status;
- exact dimensions and mode;
- preprocessing identity;
- redistribution status;
- final restricted-archive object ID when redistribution is not allowed;
- notes.

Prepared files must already be 512×512 grayscale covers and 128×128 grayscale secrets. Preprocessing is not silently performed during freeze.

## 4. Restricted data timing

Restricted inputs may remain on the persistent research server during computation. They do not trigger per-task or mid-run remote backup.

After all computation, analysis, tables, figures, manuscript, and supplement are locally complete, restricted inputs and evidence may be included in the one final client-side encrypted/private archive. The recovery key remains outside GitHub. The server must not be deleted before that final archive is uploaded and verified.

## 5. Baseline selection outcome

The two baseline slots are now selected and frozen.

### B1 — canonical grayscale k-LSB replacement

- role: simple spatial-domain capacity/distortion control;
- self-contained NumPy implementation;
- external lineage: `ragibson/Steganography`;
- pinned external commit: `06a3c920420e62f2e8a0589cfd5bfb2e51be4ee8`;
- license: MIT;
- candidate `k`: 1–4;
- clean-bit-exact candidate closest to target PSNR is selected;
- blind under plan-supplied payload length and `k`;
- Base/Detail and ECC metrics are `not_applicable`.

### B2 — blind block-DCT scalar-QIM

- role: independent transform-domain control;
- self-contained NumPy/SciPy implementation;
- external lineage: `MasonEdgar/DCT-Image-Steganography`;
- pinned external commit: `20da3e1e4d6b48dbcbe241c776ee156995bb65fe`;
- license: MIT;
- 8×8 orthonormal DCT;
- 32 frozen AC positions per block;
- exact full raw-payload capacity of 131,072 bits;
- frozen QIM delta candidates;
- bounded parity-preserving clean repair;
- clean-bit-exact candidate closest to target PSNR is selected;
- Base/Detail and ECC metrics are `not_applicable`.

The external repositories establish algorithm-family lineage. The executed B1/B2 implementations are canonical engineering controls and are not claimed as exact author-equivalent reproductions of a peer-reviewed paper.

## 6. Baseline evidence and code freeze

Authority files:

- `docs/5j/baselines/B1_CONTRACT.json`
- `docs/5j/baselines/B2_CONTRACT.json`
- `docs/5j/baselines/BASELINE_CLEAN_FIXTURE_EVIDENCE.json`
- `docs/5j/baselines/BASELINE_CODE_FREEZE.json`
- `configs/5j/baseline_registry_v1.json`

Executable validation:

```bash
python scripts/5j/validate_baseline_freeze.py --json
python -m pytest -q tests/test_5j_baselines.py
```

Any frozen-byte, external lineage, candidate parameter, capacity, clean-validity, or distortion-selection change requires a new freeze ID, rebuilt execution plan, and new run ID.

## 7. Harmonized metrics

All seven methods report common fields when applicable:

- cover-stego PSNR and SSIM;
- raw payload bits;
- protected overhead bits;
- complete recovery;
- recovered payload fraction;
- raw BER;
- reconstruction PSNR/SSIM/NCC;
- failure stage;
- runtime;
- peak memory.

Only layered internal methods report Base/Detail integrity, BER, recovery fractions, codeword outcomes, and ECC overload. Baseline layer/ECC fields must be `not_applicable` or null, never fabricated as zero.

## 8. Remaining acceptance gates

The baseline code and contracts are implementation-complete, but production execution still requires:

1. observable green repository CI or concrete CI fixes;
2. target-server clean round-trip on the actual runtime;
3. real frozen data manifests and rights evidence;
4. real calibration-only stability profile;
5. finalized source/runtime-bound execution plan;
6. engineering dry run across all seven methods.
