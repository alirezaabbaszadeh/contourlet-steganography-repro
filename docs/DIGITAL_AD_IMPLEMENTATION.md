# DIGITAL_A_D implementation and evidence contract

## Scientific boundary

`DIGITAL_A_D` is separate from P0. It never imports or applies AP/GP/HP.
P0 numerical files are protected by `docs/p0_freeze_manifest.json` and
`scripts/check_p0_frozen.py`.

| Profile | Purpose | Permitted claim |
|---|---|---|
| `proxy_directional_lp_v1` | audit the redundant contourlet-style proxy | never call it the authors' PDFB |
| `haar_orthogonal_control_v1` | exact critically sampled engineering control | never call it a Contourlet |
| approved PDFB-range v2 profile | final bounded research execution after Stage 0 v2 review | independent P3+P4 range coordinates in one explicit PDFB interpretation, not raw P4 slots or author equivalence |

The current directional proxy fails clean recovery at the fixed 45 dB
constraint and remains negative evidence. Haar exercises the software path but
does not support a contourlet performance claim.

## Controlled methods

| Method | Allocation and power | ECC |
|---|---|---|
| C0_FIXED | uniform, weight 1 | symmetric |
| C1_A | rule-based adaptive | symmetric |
| C2_D | uniform round-robin, weight 1 | unequal |
| C3_A_D | adaptive, Base in higher-score bands first | unequal |

The A score is the equal-weight mean of robust-normalized energy, variance,
64-bin absolute-coordinate entropy, and calibration-only stability. For the
final PDFB v2 profile, A is multiscale coordinate-adaptive; it is not claimed
as direct allocation over the four raw `pkva` directional arrays. Robust
normalization uses median/MAD, clips robust z-scores to ±3, and maps them to
`[0,1]`; a degenerate feature uses deterministic min-max or 0.5. Power is
`0.75 + 0.5*score`.

Capacity uses capped largest remainder with canonical band-ID tie breaking.
Every method receives exactly 222,360 unique slots and a binary
coefficient-map SHA-256.

## Distortion control

Embedding is:

```text
c' = c + lambda * weight * (2*bit - 1)
```

Lambda is selected by fixed-iteration binary search. PSNR is measured after
inverse transform, clipping, half-up rounding, and uint8 conversion. The target
is `45.0 ± 0.1 dB` and is never relaxed.

Extraction is semi-blind and analyzes both the received stego and original
cover. A bit is one when the selected coefficient difference is non-negative.

## Calibration and execution profiles

Calibration uses at most two non-reporting pairs and only:

- JPEG Q=70;
- Gaussian variance=10;
- salt-and-pepper density=0.03.

The final mandatory execution profile contains:

- Clean;
- JPEG Q=70;
- Gaussian variance=10;
- salt-and-pepper density=0.03.

The three hard profiles are independent and conditional:

- JPEG Q=50;
- Gaussian variance=15;
- salt-and-pepper density=0.05.

Each hard profile runs only C0 and C3 on four pairs after its predeclared
trigger passes. Q=90, Gaussian variance=5, and S&P density=0.01 are not part of
the research schedule. Rotation and crop remain P0 stress tests.

## Deterministic randomness

One realization is derived from the locked protocol, pair, and attack
identifiers and shared across C0-C3. The implementation may retain an internal
master value for scrambling, interleaving, or reproducible noise generation,
but there is no seed list or repeated-seed execution.

## Failure-aware outcomes

No recovered secret is fabricated after RS or CRC failure. Every decode records
failure stage, layer, and codeword index when available.

Reports include:

- decode success;
- header and payload CRC status;
- raw channel BER;
- Base/Detail BER when valid;
- known-bit fraction;
- correct-recovered-bit fraction;
- effective unrecovered-bit rate.

Unknown bits receive no recovery credit.

## Lean execution contract

```text
4 pairs x 4 methods = 16 embeddings
16 embeddings x 4 core channels = 64 mandatory result rows
3 optional families x 4 pairs x 2 methods = at most 24 added rows
absolute cap = 88 rows
```

Saved stego artifacts are reused across channel conditions. The implemented
run planner rejects:

- duplicate pair rows;
- repeated experimental seeds;
- a core count other than 64;
- C1/C2 in hard profiles;
- a total above 88.

## Commands

The durable CLI is the research execution surface:

```bash
ctsteg runtime-gate \
  --output-dir /srv/ctsteg/gates

ctsteg digital-calibrate \
  --manifest data-manifests/calibration-v2.csv \
  --config configs/digital_ad/format_v1.toml \
  --output results/calibration-v2/stability.json

ctsteg digital-research-plan \
  --manifest data-manifests/traceability-core-v2.csv \
  --config configs/digital_ad/final_locked_v1.toml \
  --stability-profile results/calibration-v2/stability.json \
  --output results/research-plan-v2.json

ctsteg digital-research-run \
  --manifest data-manifests/traceability-core-v2.csv \
  --config configs/digital_ad/final_locked_v1.toml \
  --stability-profile results/calibration-v2/stability.json \
  --runtime-gate-report /srv/ctsteg/gates/latest_runtime_gate.json \
  --output-root /srv/ctsteg/results \
  --cache-dir /srv/ctsteg/cache \
  --workers 0 \
  --require-parquet
```

The core and hard profiles, method-independent realization derivation, 64/88
validator, atomic object store, cache resume, and interruption gate are tested
code. The remaining final-run blockers are the approved PDFB adapter and
four-pair scientific data lock. The analysis remains descriptive and does not
average repeated seeds or require population-level inference.
