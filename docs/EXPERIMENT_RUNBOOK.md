# Lean experiment runbook

## Goal

Execute the smallest research study that can test A, D, their interaction, and
the full C3 method without a seed sweep or a large attack matrix.

The mandatory budget is 64 evaluation rows from 16 embeddings. Conditional
hard checks can add at most 24 rows, for an absolute cap of 88.

## Stage 0 - software and transform gates

Run the repository tests and P0 freeze check:

```bash
python -m pip install -e '.[research,test]'
python -m pytest -q
python scripts/check_p0_frozen.py
```

Prove interruption recovery on the same persistent server disk:

```bash
ctsteg runtime-gate \
  --output-dir /srv/ctsteg/gates \
  --workers 2 \
  --jobs 8
```

The final runner rejects a missing, failed, or runtime-fingerprint-mismatched
gate report. See
[`RUNTIME_EXECUTION_GATE.md`](RUNTIME_EXECUTION_GATE.md).

Generate and validate the real MATLAB PDFB Stage-0 evidence:

```bash
ctsteg pdfb-plan \
  --spec configs/digital_ad/pdfb_matlab_gate_v1.toml \
  --toolbox-path /opt/contourlet_toolbox \
  --raw-evidence results/pdfb-stage0/pdfb-audit-raw.json \
  --output results/pdfb-stage0-plan.json

ctsteg pdfb-validate \
  --spec configs/digital_ad/pdfb_matlab_gate_v1.toml \
  --evidence results/pdfb-stage0/pdfb-audit-raw.json \
  --output results/pdfb-stage0-independent-validation.json
```

Continue only after human review accepts the exact toolbox paths and hashes,
band shapes, capacity, reconstruction error, and coefficient probes. A failed
gate ends the research run; it does not trigger a proxy, payload reduction, or
larger search.

## Stage 1 - bounded data lock

Follow [`DATASET_AND_SPLIT_POLICY.md`](DATASET_AND_SPLIT_POLICY.md).

Required manifests:

```text
data-manifests/calibration-v2.csv
data-manifests/traceability-core-v2.csv
data-manifests/source-inventory-v2.csv
```

The core manifest contains exactly four rows. There are no repeated rows for
different seeds.

Run the tested data preflight. It must reject:

- a core manifest other than four unique pairs;
- duplicate pair rows;
- hash or rights failures;
- overlap with calibration inputs;
- a mandatory execution plan other than 64 rows;
- a total planned execution count above 88.

## Stage 2 - calibration

Calibration is limited to at most two non-reporting pairs and the three medium
attack conditions:

- JPEG Q=70;
- Gaussian variance=10;
- salt-and-pepper density=0.03.

```bash
ctsteg digital-calibrate \
  --manifest data-manifests/calibration-v2.csv \
  --config configs/digital_ad/format_v1.toml \
  --output results/calibration-v2/stability.json
```

The stability artifact is invalid if the transform fingerprint changes.
Calibration does not estimate a paper effect and is not repeated to search for
a favorable profile.

Freeze and inspect the exact plan:

```bash
ctsteg digital-research-plan \
  --manifest data-manifests/traceability-core-v2.csv \
  --config configs/digital_ad/format_v1.toml \
  --stability-profile results/calibration-v2/stability.json \
  --output results/research-plan-v2.json
```

The current Haar/proxy implementation requires the explicit
`--engineering-control` flag and cannot produce final PDFB evidence.

## Stage 3 - create the 16 core embeddings

Stages 3 through 5 are driven by one idempotent command:

```bash
ctsteg digital-research-run \
  --manifest data-manifests/traceability-core-v2.csv \
  --config configs/digital_ad/format_v1.toml \
  --stability-profile results/calibration-v2/stability.json \
  --runtime-gate-report /srv/ctsteg/gates/latest_runtime_gate.json \
  --output-root /srv/ctsteg/results \
  --cache-dir /srv/ctsteg/cache \
  --workers 0 \
  --require-parquet
```

Running the identical command after a process or server interruption resumes
from validated content objects. It never overwrites a completed object.

Create one stego artifact for each pair-method combination:

```text
4 pairs x 4 methods = 16 embeddings
```

Methods:

```text
C0_FIXED
C1_A
C2_D
C3_A_D
```

Every embedding must contain exactly 222,360 protected slots and meet
`45.0 ± 0.1 dB` PSNR. Save each stego image, coefficient map, lambda, payload
hash, transform fingerprint, runtime, and memory record.

Do not regenerate an embedding for each attack. Reuse the saved artifact.

## Stage 4 - mandatory 64-row core

Evaluate every saved embedding under four channel conditions:

| Channel | Pairs | Methods | Rows |
|---|---:|---:|---:|
| Clean | 4 | 4 | 16 |
| JPEG Q=70 | 4 | 4 | 16 |
| Gaussian variance=10 | 4 | 4 | 16 |
| Salt-and-pepper density=0.03 | 4 | 4 | 16 |
| **Total** |  |  | **64** |

The benchmark profile must contain only these four conditions. The same
deterministic channel realization is applied across C0-C3 for a given pair and
attack.

Clean requirements:

- all four methods execute on all four pairs;
- header and payload CRC status is retained;
- every successful clean decode is bit-exact;
- PSNR remains within tolerance;
- failures are stored, not discarded.

An algorithmic clean failure blocks attacked evaluation until classified. If
the failure is an inherent method result rather than a software defect, retain
it as negative evidence and stop expansion.

## Stage 5 - decide conditional hard checks

Evaluate each attack family independently using the trigger in
[`RESEARCH_PROTOCOL.md`](RESEARCH_PROTOCOL.md).

For a triggered family, evaluate only C0 and C3 on all four pairs:

| Family | Hard point | Added rows |
|---|---|---:|
| JPEG | Q=50 | 8 |
| Gaussian | variance=15 | 8 |
| Salt-and-pepper | density=0.05 | 8 |

Record one of these statuses for every family:

```text
not_triggered
triggered_and_run
blocked_by_clean_gate
blocked_by_incomplete_core
blocked_by_operational_failure
```

The maximum addition is 24 rows. Q=90, variance=5, density=0.01, C1, and C2
are not scheduled in this stage.

## Stage 6 - analysis

Generate a single long-form table containing:

- pair, method, channel, and fixed operating-point identifiers;
- EUR and raw BER;
- Base and Detail recovery when valid;
- header and payload CRC state;
- PSNR and SSIM;
- capacity and selected lambda;
- runtime, memory, and failure state.

For each core pair and channel, compute:

```text
A  = ((C0-C1) + (C2-C3)) / 2
D  = ((C0-C2) + (C1-C3)) / 2
AD = C1 + C2 - C0 - C3
FULL = C0-C3
```

Report raw rows, mean, median, range, and direction count. Do not run a
10,000-resample bootstrap, sign-flip, Wilcoxon, Holm family, or achieved-power
analysis for four cases.

## Stage 7 - stop or report

Stop after the mandatory core when C3 has no meaningful advantage and results
are not saturated. A neutral or negative result is complete research evidence.

Do not add images, seeds, attack levels, retries, or parameter searches to make
the result positive.

Permitted reruns are limited to documented operational failures. Reuse the same
inputs and realization identifier and retain the failed artifact.

## Evidence package

Archive:

- source commit and clean/dirty status;
- PDFB raw evidence, validator output, and human review;
- four-row manifest and all input hashes;
- config and transform fingerprint;
- 16 stego artifacts;
- 64 mandatory result rows;
- 0-24 conditional result rows;
- trigger decisions for all three families;
- automatically generated tables and figures;
- runtime interruption-gate report and resource plan;
- failed attempts, stale locks, and quarantine records when present;
- checksum inventory and updated claim matrix.

The release fails if the mandatory count is not exactly 64 or if the total
exceeds 88 without a new approved protocol.
