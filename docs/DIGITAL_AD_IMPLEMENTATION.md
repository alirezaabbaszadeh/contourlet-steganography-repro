# DIGITAL_A_D implementation and evidence contract

## Scientific boundary

`DIGITAL_A_D` is separate from P0. It never imports or applies AP/GP/HP.
P0 numerical files are protected by `docs/p0_freeze_manifest.json` and
`scripts/check_p0_frozen.py`.

Two executable transform profiles are intentionally distinguished:

| Profile | Purpose | Permitted claim |
|---|---|---|
| `proxy_directional_lp_v1` | Audit the existing redundant contourlet-style proxy | Never call it the authors' PDFB |
| `haar_orthogonal_control_v1` | Exact critically sampled engineering control for C0–C3 implementation and tests | Never call it a Contourlet |

The redundant proxy reconstructs analyzed images exactly, but its directional
arrays are not independently writable coefficients. A measured pilot at the
45 dB constraint produced about 39% raw clean bit error after inverse and
re-analysis, so the run correctly fails instead of reducing the quality target.

The Haar control supplies four independent 256×256 subbands (262,144
coefficients) and allows every software stage to be exercised. A paper claim
against the source article still requires an approved PDFB adapter or author
parameters. Results from the Haar control are engineering controls, not
Contourlet superiority evidence.

## Controlled methods

| Method | Allocation and power | ECC |
|---|---|---|
| C0_FIXED | uniform, weight 1 | symmetric |
| C1_A | rule-based adaptive | symmetric |
| C2_D | uniform round-robin, weight 1 | unequal |
| C3_A_D | adaptive, Base in higher-score bands first | unequal |

The A score is the equal-weight mean of robust-normalized energy, variance,
64-bin absolute-coefficient entropy, and calibration-only stability. Robust
normalization uses median/MAD, clips robust z-scores to ±3, and maps them to
`[0,1]`; a degenerate feature uses deterministic min-max or 0.5. The power is
`0.75 + 0.5*score`.

Capacity is assigned by capped largest remainder with canonical band-ID tie
breaking. Every slot plan contains exactly 222,360 unique entries and carries
a binary coefficient-map SHA-256.

## Distortion control

Embedding is:

```text
c' = c + lambda * weight * (2*bit - 1)
```

The global lambda is selected by fixed-iteration binary search. PSNR is
measured after inverse transform, clipping, half-up rounding, and uint8
conversion. The largest feasible value inside the configured interval is
retained. The target is never silently relaxed.

Extraction is semi-blind and analyzes both the received stego and original
cover. A bit is one when the selected coefficient difference is non-negative.

## Calibration and attacks

Stability is generated only with `digital-calibrate` from a manifest whose
split label starts with `calibration`. The fixed attacks are JPEG Q=70,
Gaussian variance 10, and salt-and-pepper density 0.03. The stored transform
fingerprint must match a later run.

The digital final suite contains only:

- JPEG qualities 90, 70, 50;
- Gaussian variances 5, 10, 15;
- salt-and-pepper densities 0.01, 0.03, 0.05.

Rotation and crop remain P0 stress tests and are never included in a digital
robustness claim.

## Failure-aware outcomes

No fake recovered secret is created after RS or CRC failure. Every decode
returns failure stage, layer, and codeword index when available.

To avoid survivor bias, reports include:

- decode success;
- header and payload CRC status;
- raw channel BER;
- Base/Detail BER when that layer is valid;
- known-bit fraction;
- correct-recovered-bit fraction;
- effective unrecovered-bit rate, where an unknown bit receives no recovery
  credit rather than an invented value.

## Commands

```bash
ctsteg audit-transform \
  --config configs/digital_ad/proxy_audit_v1.toml \
  --output results/proxy-audit.json

ctsteg digital-demo \
  --config configs/digital_ad/stage3_pilot.toml \
  --method C3_A_D \
  --attack-profile pilot \
  --output-dir results/digital-demo

ctsteg digital-calibrate \
  --manifest data/calibration.csv \
  --config configs/digital_ad/format_v1.toml \
  --output results/stability-v1.json

ctsteg digital-benchmark \
  --manifest data/locked-test.csv \
  --config configs/digital_ad/final_locked_v1.toml \
  --stability-profile results/stability-v1.json \
  --output-dir results/final-v1

ctsteg digital-factorial \
  --results results/final-v1/results_long.csv \
  --output-dir results/factorial-v1
```

The factorial report calculates A and D main effects,
`C3-C2-C1+C0` interaction, and all preregistered pairwise contrasts. Repeated
seeds are averaged within image pair before inference.
