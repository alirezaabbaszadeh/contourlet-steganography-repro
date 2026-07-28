# MATLAB PDFB Stage-0 transform gate

## Purpose

This gate tests one explicit interpretation of Minh Do's MATLAB Contourlet
Toolbox before it can be considered for the `DIGITAL_A_D` carrier. It never
identifies that interpretation as the source paper's undisclosed transform.

The toolbox is an external dependency and is not vendored. The reference
implementation is distributed through
[MATLAB File Exchange](https://www.mathworks.com/matlabcentral/fileexchange/8837-contourlet-toolbox).
Its documented `pdfbdec` output stores the low-pass image in the first cell
and pyramid detail levels from coarse to fine in subsequent cells.

## Locked interpretation

[`pdfb_matlab_gate_v1.toml`](../configs/digital_ad/pdfb_matlab_gate_v1.toml)
records:

- pyramid filter `9-7`;
- directional filter `pkva`;
- directional depths `[2, 2, 2, 2]`;
- fourth pyramid level from coarse as the candidate pool;
- 512×512 deterministic audit input;
- 222,360 required coefficient slots;
- three interior coefficient probes per eligible directional band.

These values are documented assumptions inherited from the repository's
existing MATLAB path. They are not reverse-engineered paper parameters.

## What MATLAB measures

[`audit_pdfb_stage0.m`](../matlab/audit_pdfb_stage0.m) resolves `pdfbdec` and
`pdfbrec` from the supplied toolbox directory and records their SHA-256
identities. It then records:

1. every low-pass and directional band ID, shape, and coefficient count;
2. exact candidate capacity without assuming 262,144 coefficients;
3. analysis/synthesis reconstruction error;
4. total redundancy;
5. representative coefficient write/read probes.

Each probe adds one unit to one selected coefficient, synthesizes the image,
reanalyzes it, and measures:

- gain at the intended coefficient;
- maximum change at every other eligible coefficient;
- total off-target L2 energy.

The comparison uses an unmodified synthesis/reanalysis as its reference so
that the probe isolates the perturbation rather than baseline projection
error.

## Quantitative gates

| Check | Locked criterion |
|---|---:|
| Eligible directions | exactly 4 |
| Candidate capacity | at least 222,360 |
| Reconstruction maximum error | at most `1e-8` |
| Probe coverage | at least 3 per eligible band |
| Minimum intended self-gain | at least `0.99` |
| Maximum cross-talk | at most `0.01` |
| Maximum off-target L2 ratio | at most `0.05` |

A failed threshold is valid negative evidence and produces
`gate_passed=false`. A malformed artifact, changed parameter, wrong input
hash, missing runtime identity, or toolbox hash mismatch is rejected.

## Commands

Generate a reviewable command plan without requiring MATLAB:

```bash
ctsteg pdfb-plan \
  --spec configs/digital_ad/pdfb_matlab_gate_v1.toml \
  --toolbox-path /absolute/path/to/contourlet_toolbox \
  --raw-evidence results/pdfb-stage0/pdfb-audit-raw.json \
  --output results/pdfb-stage0-plan.json
```

Run the real external audit:

```bash
ctsteg pdfb-audit \
  --spec configs/digital_ad/pdfb_matlab_gate_v1.toml \
  --toolbox-path /absolute/path/to/contourlet_toolbox \
  --matlab-scripts matlab \
  --timeout-seconds 1800 \
  --output-dir results/pdfb-stage0
```

Validate evidence copied from another machine:

```bash
ctsteg pdfb-validate \
  --spec configs/digital_ad/pdfb_matlab_gate_v1.toml \
  --evidence results/pdfb-audit-raw.json \
  --output results/pdfb-gate-validation.json
```

The runtime command is passed to MATLAB as an argument vector, not through a
shell. Existing non-empty evidence and output directories are never replaced.

## Meaning of a pass

A Stage-0 pass means only that this explicit toolbox/filter/schedule
combination has sufficient measured capacity, reconstruction quality, and
representative coefficient writability to receive human review.

It does **not**:

- enable a Python PDFB embedding profile;
- permit a bulk or locked-test benchmark;
- establish author-equivalent reproduction;
- permit a direct superiority claim against the paper.

The next gate after a pass is review of the raw probes and implementation of a
versioned runtime adapter with clean C0 recovery at the locked 45 dB PSNR
constraint.
