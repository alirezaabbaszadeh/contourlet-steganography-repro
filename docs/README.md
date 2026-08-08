# Research documentation map

This directory is the documentation control plane for the independent
reconstruction and the prospective `DIGITAL_A_D` study. It separates reported
facts, executable contracts, unverified interpretations, and future claims so
that a software result cannot silently become a paper claim.

## Authority order

When two descriptions appear inconsistent, use this order:

1. frozen source, versioned configuration, input manifest, and raw evidence;
2. machine-checked format and stage-gate contracts;
3. the prospective research protocol and decision log;
4. explanatory guides and manuscript planning documents;
5. values reported by the source article.

The source article's numbers are external targets. They never override
measured output or a failed gate.

## Project tracks

| Track | Purpose | Current scientific status |
|---|---|---|
| `P0_FROZEN` | Independent reconstruction of Kumar et al. (2026) | Executable and audited, but not author-equivalent |
| `DIGITAL_A_D` | New Base/Detail digital transport and C0-C3 factorial study | Software implemented; final scientific run not executed |
| `TRANSFORM_PROFILES` | Proxy, Haar control, and explicit MATLAB PDFB interpretation | Proxy and Haar tested; MATLAB PDFB runtime evidence pending |
| `EVALUATION` | Four-pair manifest, lean attack profiles, metrics, and descriptive contrasts | Durable parallel/cache/resume runner and 64/88 guard implemented; final PDFB/data lock pending |

## Start here

### Project and governance

- [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) - mission, scope, immutable
  constraints, claim hierarchy, and definitions of done.
- [`DECISION_LOG.md`](DECISION_LOG.md) - dated architectural and scientific
  decisions. A changed decision requires a new entry.
- [`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md) - lean work packages,
  dependencies, cost caps, acceptance criteria, and stop rules.
- [`STAGE_GATE_STATUS.md`](STAGE_GATE_STATUS.md) - implemented stages and
  current blockers.
- [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) - evidence and manuscript
  release gates.

### Reproduction and transform boundary

- [`REPRODUCIBILITY_AUDIT.md`](REPRODUCIBILITY_AUDIT.md) - omissions,
  contradictions, and interpretations in the source article.
- [`PAPER_TARGETS.csv`](PAPER_TARGETS.csv) - reported, not reproduced, values.
- [`PDFB_TRANSFORM_GATE.md`](PDFB_TRANSFORM_GATE.md) - fail-closed MATLAB
  Stage-0 audit.
- [`PDFB_TRANSFORM_GATE_FA.md`](PDFB_TRANSFORM_GATE_FA.md) - Persian PDFB
  gate guide.

### Proposed method and experiments

- [`DIGITAL_AD_FORMAT_V1.md`](DIGITAL_AD_FORMAT_V1.md) - bit-exact transport
  format.
- [`DIGITAL_AD_IMPLEMENTATION.md`](DIGITAL_AD_IMPLEMENTATION.md) - executable
  A+D and evidence contract.
- [`RESEARCH_PROTOCOL.md`](RESEARCH_PROTOCOL.md) - prospective research
  questions, estimands, success rules, and analysis policy.
- [`DATASET_AND_SPLIT_POLICY.md`](DATASET_AND_SPLIT_POLICY.md) - four-case
  acquisition, preprocessing, pairing, deterministic-realization, and freeze rules.
- [`EXPERIMENT_RUNBOOK.md`](EXPERIMENT_RUNBOOK.md) - operational sequence and
  commands from a clean checkout to an evidence package.
- [`RUNTIME_EXECUTION_GATE.md`](RUNTIME_EXECUTION_GATE.md) - parallel workers,
  content cache, interruption recovery, export, and systemd contract.
- [`RUNTIME_EXECUTION_GATE_FA.md`](RUNTIME_EXECUTION_GATE_FA.md) - concise
  Persian server and resume guide.
- [`SERVER_DEPLOYMENT.md`](SERVER_DEPLOYMENT.md) - pinned Ubuntu, MATLAB,
  toolbox, data, systemd, resource-monitor, and ETA deployment contract.
- [`SERVER_DEPLOYMENT_FA.md`](SERVER_DEPLOYMENT_FA.md) - complete Persian
  server provisioning and operations guide.
- [`NOVELTY_PROTOCOL.md`](NOVELTY_PROTOCOL.md) - novelty and prior-art rules.

### Claims and paper writing

- [`CLAIMS_AND_EVIDENCE.md`](CLAIMS_AND_EVIDENCE.md) - claim ladder, allowed
  wording, blocked wording, and result-dependent decisions.
- [`CLAIM_EVIDENCE_MATRIX.csv`](CLAIM_EVIDENCE_MATRIX.csv) - machine-readable
  claim status and minimum evidence.
- [`MANUSCRIPT_BLUEPRINT.md`](MANUSCRIPT_BLUEPRINT.md) - article structure,
  tables, figures, and positive, neutral, or negative result paths.

### Existing benchmark guides

- [`BENCHMARKING.md`](BENCHMARKING.md) - original P0-compatible batch and
  paired-comparison harness.
- [`BENCHMARKING_FA.md`](BENCHMARKING_FA.md) - Persian P0 benchmark guide.
- [`DIGITAL_AD_FA.md`](DIGITAL_AD_FA.md) - concise Persian C0-C3 guide.
- [`RESEARCH_MASTER_PLAN_FA.md`](RESEARCH_MASTER_PLAN_FA.md) - complete Persian
  project, experiment, and manuscript plan.
- [`README_FA.md`](README_FA.md) - short Persian repository entry point.

## Two non-interchangeable experiment contracts

The repository intentionally retains two different contracts:

| Contract | Cover | Secret | Purpose |
|---|---:|---:|---|
| P0 analogue reconstruction | 512x512 | 512x512 | Trace and audit the article |
| `DIGITAL_A_D` format v1 | 512x512 | 128x128 | Controlled digital A+D experiment |

Their raw metrics are not a direct head-to-head comparison. A claim against
the article requires a harmonized, approved PDFB comparison or wording limited
to the controlled digital case study.

## Lean execution budget

| Item | Count |
|---|---:|
| Traceability pairs | 4 |
| Core embeddings | 16 |
| Mandatory rows | 64 |
| Conditional hard rows | 0-24 |
| Absolute cap | 88 |
| Scientific seed repetitions | 0 |

The final matrix keeps C0-C3 only in Clean and one representative condition
per attack family. Hard conditions run only for C0/C3 after a predeclared
trigger. A neutral or negative core result does not authorize expansion.

## Documentation update rule

Every outcome-determining change must update all applicable items:

1. configuration or format contract;
2. tests;
3. decision log;
4. stage-gate status;
5. claim/evidence matrix;
6. runbook and manuscript plan if the evidence path changed.

Documentation must describe failed and negative runs. It must never replace
them with a successful example, tune a threshold after seeing locked results,
or describe a proxy as the paper's undisclosed transform.

## Source article

The baseline reference is:

> R. Kumar, S. Singhal, and V. K. Sharma, "Efficient image steganography
> method using contourlet transform and geometric-based pixel encryption for
> enhanced security," Scientific Reports 16, 16771 (2026).
> https://doi.org/10.1038/s41598-026-41168-0

The article, its figures, and third-party datasets are linked and cited, not
redistributed by this repository.
