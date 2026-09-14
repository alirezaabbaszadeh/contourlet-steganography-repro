# FINAL-5J-v1 Typed Result Schema

Status: **implementation contract**

The 5J runner must write immutable, content-addressed embedding and evaluation objects. A binary success flag is insufficient; every object must preserve enough typed information to reproduce the planned failure-severity, paired, runtime, and backup analyses.

## 1. Object classes

- `embedding`: one pair × method × payload fraction × PSNR target;
- `evaluation`: one embedding × channel instance;
- `run_summary`: exact plan, completed/failed/backed-up counts, object roots, and freeze identities;
- `codeword_diagnostics`: optional normalized child records referenced by an evaluation when full per-codeword evidence is stored separately;
- `backup_ledger`: remote persistence and verification state.

The previous format-v1 objects retain their existing schema and namespace. 5J objects use new schema IDs and may never overwrite historical objects.

## 2. Required identity dimensions

Every content identity must include all outcome-determining dimensions:

- `FINAL-5J-v1` protocol ID and payload format version;
- exact numerical source fingerprint;
- exact pair/input hashes;
- method, including baseline source commit and adapter fingerprint;
- payload fraction and target PSNR;
- transform/config/stability fingerprints;
- channel family, severity, realization ID, and pair-derived seed;
- decoder and metric implementation fingerprints.

Omitting any such dimension from object identity is a cache-collision defect.

## 3. Validity and failure fields

Each evaluation records:

- `validity_state` from the format-v2 contract;
- `complete_recovery`, `valid_base_only_recovery`;
- header, complete payload, Base, and Detail integrity decisions;
- S0–S6 `failure_stage`;
- scientific versus operational status;
- all explicit failure records;
- Base/Detail BER and recovery fractions;
- recovered/unknown payload fractions;
- codeword success, failure, corrected-symbol, and ECC-overload summaries.

Unavailable semantic fields for non-layered baselines are `null` with applicability `not_applicable`; they are never encoded as zero.

## 4. Metrics

Required common metrics where meaningful:

- cover–stego MSE, PSNR, and SSIM;
- complete recovered-secret BER, MSE, PSNR, SSIM, and NCC;
- valid Base-only reconstruction MSE, PSNR, SSIM, and NCC;
- raw extracted-bit BER;
- payload, Base, Detail, and unknown-bit fractions;
- runtime breakdown, peak RSS, and I/O counts.

Metric values are JSON numbers or `null`. Strings such as `nan` and `inf` are prohibited in typed scientific objects.

## 5. Codeword diagnostics

For every Base and Detail codeword, the normalized evidence should retain when available:

- index and RS profile;
- data/parity symbols and correction radius;
- decoder status and corrected-symbol count;
- observed symbol-error count when ground-truth comparison is available;
- `ecc_overload = max(0, observed_errors - correction_radius)`;
- failure reason.

Evaluation-level summaries include successful and failed codeword counts, total corrected symbols, maximum/mean/median overload, and fraction at or below radius.

## 6. Completeness

A run is not complete merely because all computations exited. `run_summary` must reconcile exactly:

- 530 planned embeddings;
- 8,420 planned evaluations;
- every planned identity appearing once;
- no unplanned scientific object;
- no duplicate object identity;
- explicit operational failure objects rather than missing rows;
- every complete object having a verified remote backup ledger entry.

## 7. Serialization

Canonical JSON is authoritative. JSONL, CSV, and Parquet are deterministic projections generated from the canonical objects. Projection schemas must preserve nullability and applicability and must not infer missing values.

Final tables and figures are generated from canonical or validated projected data; no result value is hand-copied into the manuscript.