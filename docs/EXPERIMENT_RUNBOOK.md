# Experiment runbook

## Purpose

This runbook is the operational path from a clean checkout to a reviewable
evidence package. It does not authorize skipping a gate. Commands that require
external MATLAB or final data are shown for the approved environment and must
not be simulated in Python-only CI.

## Run states

| State | Meaning |
|---|---|
| `development` | Code and synthetic/pilot inputs may change |
| `gate-review` | Transform and clean evidence are under review |
| `calibration` | A stability is estimated from calibration-only data |
| `protocol-lock` | Code, config, data, seeds, and analyses are immutable |
| `final-run` | Locked units execute once |
| `analysis-lock` | Raw results are immutable; only preregistered analysis runs |
| `release-candidate` | Tables, figures, claims, and archives are verified |

## 0. Clean checkout

```bash
git clone https://github.com/alirezaabbaszadeh/contourlet-steganography-repro.git
cd contourlet-steganography-repro
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

On Windows PowerShell, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

Record:

```bash
git rev-parse HEAD
git status --porcelain
python --version
python -m pip freeze
```

The final run requires an empty `git status --porcelain`.

## 1. Repository validation

```bash
python -m unittest discover -s tests -v
python scripts/check_p0_frozen.py
python -m compileall -q src tests
```

Pass conditions:

- all tests pass;
- all six P0 hashes match;
- source compilation succeeds;
- no result fixture was edited to force a target value.

Stop if any condition fails.

## 2. Transform inventory

### Python profiles

```bash
ctsteg audit-transform \
  --config configs/digital_ad/proxy_audit_v1.toml \
  --output results/proxy-audit.json

ctsteg audit-transform \
  --config configs/digital_ad/format_v1.toml \
  --output results/haar-control-audit.json
```

Interpretation:

- the proxy audit is diagnostic and may fail the clean coefficient channel;
- the Haar audit validates the engineering control only;
- neither output establishes the article's PDFB identity.

### MATLAB Stage-0 plan

This command does not execute MATLAB:

```bash
ctsteg pdfb-plan \
  --spec configs/digital_ad/pdfb_matlab_gate_v1.toml \
  --toolbox-path /absolute/path/to/contourlet_toolbox \
  --raw-evidence results/pdfb-stage0/pdfb-audit-raw.json \
  --output results/pdfb-stage0-plan.json \
  --matlab-scripts matlab
```

Review the generated argument vector, absolute paths, spec hash, and claim
boundary.

### MATLAB Stage-0 execution

Run only on a machine with MATLAB and a user-provided Minh Do Contourlet
Toolbox installation:

```bash
ctsteg pdfb-audit \
  --spec configs/digital_ad/pdfb_matlab_gate_v1.toml \
  --toolbox-path /absolute/path/to/contourlet_toolbox \
  --matlab-scripts matlab \
  --timeout-seconds 1800 \
  --output-dir results/pdfb-stage0
```

Expected files:

- `execution-plan.json`;
- `gate-spec.json`;
- `stdout.log`;
- `stderr.log`;
- `runtime-status.json`;
- `pdfb-audit-raw.json`;
- `pdfb-gate-validation.json`.

Independently revalidate copied evidence:

```bash
ctsteg pdfb-validate \
  --spec configs/digital_ad/pdfb_matlab_gate_v1.toml \
  --evidence results/pdfb-stage0/pdfb-audit-raw.json \
  --output results/pdfb-stage0-independent-validation.json
```

### Human review

Before adapter development, review:

- MATLAB version, release, and platform;
- resolved toolbox paths and hashes;
- every band shape and coefficient count;
- exact candidate capacity;
- reconstruction error;
- each raw probe location, self-gain, cross-talk, and off-target ratio;
- consistency between raw and independently validated aggregates.

A machine pass remains `eligible_for_human_review`. Record the human decision
in a versioned review file. Do not vendor the external toolbox.

## 3. Data acquisition and preflight

Follow [`DATASET_AND_SPLIT_POLICY.md`](DATASET_AND_SPLIT_POLICY.md).

The final repository must contain acquisition instructions and manifests, not
unauthorized image copies. Generate separate files such as:

```text
data-manifests/calibration-v1.csv
data-manifests/pilot-v1.csv
data-manifests/locked-test-v1.csv
data-manifests/source-inventory-v1.csv
```

Each final pair appears five times, once for seeds 2026 through 2030.

Before lock, run the required duplicate/leakage preflight. This command is a
planned implementation gate; the final study must not begin until a tested
CLI exists and its artifact is stored:

```text
ctsteg data-preflight ...
```

Do not replace this gate with manual visual inspection.

## 4. Calibration

Create stability only from the calibration manifest:

```bash
ctsteg digital-calibrate \
  --manifest data-manifests/calibration-v1.csv \
  --config configs/digital_ad/format_v1.toml \
  --output results/calibration-v1/stability.json
```

Verify:

- the split begins with `calibration`;
- the transform fingerprint matches the intended final profile;
- attacks are JPEG 70, Gaussian variance 10, and salt-and-pepper density 0.03;
- source manifest and artifact hashes are retained.

If the final transform changes, discard this stability artifact and recalibrate
under a new version.

## 5. Clean gate

Run all methods with no attacks on pilot data:

```bash
ctsteg digital-benchmark \
  --manifest data-manifests/pilot-v1.csv \
  --config configs/digital_ad/final_locked_v1.toml \
  --methods C0_FIXED C1_A C2_D C3_A_D \
  --stability-profile results/calibration-v1/stability.json \
  --attack-profile none \
  --output-dir results/clean-gate-v1
```

Required:

- all units execute;
- every method decodes cleanly;
- payload and header CRCs pass;
- PSNR remains inside the locked target;
- coefficient maps contain exactly 222,360 unique slots;
- outputs and hashes are complete.

An algorithmic clean failure blocks the final run. Do not lower PSNR, payload,
or ECC requirements to pass.

## 6. Pilot

Use only development/pilot pairs:

```bash
ctsteg digital-benchmark \
  --manifest data-manifests/pilot-v1.csv \
  --config configs/digital_ad/stage3_pilot.toml \
  --methods C0_FIXED C1_A C2_D C3_A_D \
  --stability-profile results/calibration-v1/stability.json \
  --attack-profile pilot \
  --output-dir results/pilot-v1

ctsteg digital-factorial \
  --results results/pilot-v1/results_long.csv \
  --output-dir results/pilot-factorial-v1 \
  --bootstrap-resamples 10000 \
  --permutation-resamples 10000 \
  --seed 2026
```

Pilot results may diagnose code, estimate variance, and support power
calculation. They may not select a favorable final endpoint or attack.

## 7. Protocol lock

Do not lock until these planned components exist:

- tested data preflight;
- tested attack-averaged primary analysis;
- protocol-lock artifact generator;
- table and figure generator;
- approved transform runtime adapter if contourlet claims are intended.

The lock artifact must contain SHA-256 identities for:

- source commit and dirty status;
- digital format and final config;
- transform profile and runtime evidence;
- calibration stability;
- source inventory and all manifests;
- attack and metric implementations;
- primary and secondary analysis implementations;
- planned seed set and sample-size decision;
- documentation protocol version.

Write the lock artifact before final outputs exist. Sign or independently copy
its hash to a durable location.

## 8. Final benchmark

Create a new, absent output directory:

```bash
ctsteg digital-benchmark \
  --manifest data-manifests/locked-test-v1.csv \
  --config configs/digital_ad/final_locked_v1.toml \
  --methods C0_FIXED C1_A C2_D C3_A_D \
  --stability-profile results/calibration-v1/stability.json \
  --attack-profile final \
  --output-dir results/final-v1
```

Do not use `--continue-on-error` to make a paper run appear complete. If an
operational error interrupts execution:

1. retain the incomplete directory;
2. record the failure;
3. diagnose without viewing selective method outcomes where possible;
4. version the rerun decision;
5. rerun the full affected protocol, not only favorable cells.

Algorithmic decode failures remain final outcomes.

## 9. Analysis

Secondary per-condition factorial analysis:

```bash
ctsteg digital-factorial \
  --results results/final-v1/results_long.csv \
  --output-dir results/factorial-v1 \
  --bootstrap-resamples 10000 \
  --permutation-resamples 10000 \
  --seed 2026
```

The preregistered primary analysis is the attack-averaged C3 versus C0
effective unrecovered-bit rate. Its CLI is a required future implementation.
The final run is blocked until the tested command and exact output schema are
documented here.

Primary analysis must:

- average seeds within pair and attack;
- average the nine attacks equally within pair;
- compute `C0-C3`;
- report the 0.01 practical threshold;
- generate paired bootstrap and sign-flip results;
- retain every pair-level primary value.

## 10. Evidence integrity

Generate a checksum inventory without modifying evidence:

```bash
find results/final-v1 results/factorial-v1 -type f -print0 \
  | sort -z \
  | xargs -0 sha256sum \
  > evidence-sha256.txt
```

Record:

- command history or run script;
- UTC start and end;
- hardware and operating system;
- Python and dependency versions;
- MATLAB and toolbox identities when used;
- CPU thread environment;
- original protocol-lock hash;
- result and analysis directory hashes.

Copy the immutable evidence package to at least two durable locations before
writing conclusions.

## 11. Tables and figures

All manuscript artifacts are generated from raw CSV/JSON:

- no spreadsheet transcription;
- no manual deletion of failed pairs;
- no favorable-axis truncation;
- no hidden post-processing;
- reported source values remain visibly labelled as external.

Each generated table or figure stores source hashes and generator commit.

## 12. Claim review and release

Update:

- [`CLAIM_EVIDENCE_MATRIX.csv`](CLAIM_EVIDENCE_MATRIX.csv);
- [`CLAIMS_AND_EVIDENCE.md`](CLAIMS_AND_EVIDENCE.md);
- [`STAGE_GATE_STATUS.md`](STAGE_GATE_STATUS.md);
- [`DECISION_LOG.md`](DECISION_LOG.md);
- [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md).

Only rows with sufficient evidence may become manuscript claims.

## Failure branches

| Failure | Required response |
|---|---|
| PDFB capacity below 222,360 | Preserve negative evidence; do not reduce payload |
| PDFB probe gate fails | Do not enable adapter |
| Clean C0 fails | Stop pilot/final execution |
| Adaptive stability fingerprint mismatches | Recalibrate on correct transform |
| Data leakage found | Rebuild all affected splits before lock |
| Primary rule fails | Publish neutral, mixed, or negative conclusion |
| Direct article harmonization is impossible | Limit claims to controlled digital factorial study |
