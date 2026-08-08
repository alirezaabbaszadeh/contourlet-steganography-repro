# 5J Comparative Failure-Severity Specification

Status: implementation baseline  
Protocol: `FINAL-5J-v1`

## 1. Purpose

Binary recovery alone cannot distinguish a near-threshold ECC failure from header loss, catastrophic extraction failure, or a stream that retains a valid Base layer. 5J therefore treats failure mechanism and failure distance as first-class outputs.

Scientific failure and operational failure must never be pooled.

## 2. Primary failure stage

Each evaluation has exactly one primary stage:

| Code | Meaning |
|---|---|
| `S0_COMPLETE` | complete payload and all required integrity checks valid |
| `S1_BASE_ONLY` | Base valid, complete payload invalid because Detail is invalid or unavailable |
| `S2_HEADER_VALID_PARTIAL` | header valid and partial decoded information exists, but no layer passes integrity |
| `S3_PAYLOAD_ECC_FAILURE` | required payload codewords exceed correction capability |
| `S4_HEADER_FAILURE` | header cannot be validated or decoded sufficiently to continue |
| `S5_EXTRACTION_TRANSFORM_FAILURE` | transform/extraction boundary fails before a valid payload decision |
| `S6_OPERATIONAL_FAILURE` | software, resource, environment, storage, or infrastructure failure |

Priority is determined by the deepest scientifically valid state reached. `S6_OPERATIONAL_FAILURE` is assigned only when the intended scientific evaluation did not complete reliably.

## 3. Layer validity

Required fields:

- `header_valid`: boolean;
- `base_integrity`: `valid`, `invalid`, `not_applicable`, or `not_evaluated`;
- `detail_integrity`: same enum;
- `complete_integrity`: same enum;
- `diagnostic_unverified`: boolean.

A Base-only recovery is valid only if Base integrity is independently valid. Ground-truth similarity cannot convert an invalid decode into a valid decode.

## 4. Codeword-level evidence

For every required codeword, record:

- layer;
- codeword index;
- code parameters and correction radius `t_i`;
- observed symbol errors `e_i` when ground-truth diagnostic comparison is permitted;
- decoder status;
- corrected-symbol count;
- erasure count, if applicable;
- overload `O_i = max(0, e_i - t_i)`.

Required layer summaries:

- codeword count;
- successful and failed codeword counts;
- fraction within correction radius;
- total corrected symbols;
- mean, median, maximum, and sum of overload;
- worst required-codeword distance beyond radius.

If a baseline does not expose ECC codewords, these fields are `not_applicable`; a common recovered-bit metric remains mandatory.

## 5. Recovery fractions

Required common metrics:

- correctly recovered protected-payload fraction;
- correctly recovered raw-secret fraction;
- secret BER;
- unknown-bit fraction;
- reconstructed-secret PSNR, SSIM, MSE, and NCC where defined.

Required hierarchical metrics:

- Base recovery fraction and BER;
- Detail recovery fraction and BER;
- valid Base-only indicator;
- Base-only reconstruction quality.

An unverified diagnostic reconstruction must be labelled and reported separately from valid outputs.

## 6. Comparative failure gap

Within matched pair, method, attack family, severity, and realization, report paired differences for:

- failure-stage ordering;
- recovered-secret fraction;
- Base recovery fraction where applicable;
- failed-codeword count;
- ECC overload summaries;
- reconstruction quality;
- distance to the nearest observed successful severity.

Stage ordering is descriptive and must not be averaged as if equally spaced. Statistical comparison uses endpoint-specific methods defined in the Statistical Analysis Plan.

## 7. Boundary reporting

For each method and attack family, produce severity-dependent curves for:

- complete recovery rate;
- valid Base-only recovery rate;
- recovered-secret fraction;
- Base and Detail BER;
- failure-stage distribution;
- ECC overload;
- reconstructed-secret quality.

A report must distinguish at least these cases:

1. near-threshold ECC overload;
2. multiple severe codeword failures;
3. header loss;
4. valid Base preservation with Detail loss;
5. extraction/transform failure;
6. operational failure.

## 8. Missing and unavailable values

Use typed states rather than ambiguous nulls:

- `not_applicable`: metric has no meaning for this method;
- `not_evaluated`: evaluation did not reach the measurement stage;
- `missing_operational`: expected value absent because of an operational failure;
- numeric/boolean value: measurement exists.

Zero must never substitute for unavailable data.

## 9. Acceptance tests

Synthetic fixtures must cover all S0–S6 stages, including:

- complete valid recovery;
- valid Base with invalid Detail;
- header-valid partial data with invalid layer integrity;
- one-codeword overload of exactly one symbol;
- severe overload across multiple codewords;
- header failure;
- transform/extraction exception;
- resource or upload failure.

The schema and analysis code must reject contradictory states, including `S1_BASE_ONLY` with invalid Base integrity or `S0_COMPLETE` with any required integrity failure.
