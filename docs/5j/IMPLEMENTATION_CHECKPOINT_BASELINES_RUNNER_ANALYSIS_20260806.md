# FINAL-5J-v1 checkpoint: baselines, runner, data freeze, analysis, and final archive

Date: 2026-08-06  
Branch: `agent/runtime-resume-gate`  
Checkpoint head before this document: `68e3ebb36871628abde61652cf78aca123e92820`

## Author decisions preserved

- Numerical execution uses local atomic/cache objects and local resume.
- Remote backup does not run during embeddings, evaluations, sweeps, or analysis.
- One final archive is built, uploaded, and verified only after the entire project and manuscript package are locally complete.
- No plaintext private key, PEM, token, password, license credential, or recovery key may enter Git or an archive.

## Baselines completed and frozen

### B1

- canonical grayscale k-LSB replacement;
- clean-valid `k` chosen from `{1,2,3,4}` by closest realized PSNR;
- external lineage pinned to `ragibson/Steganography` commit `06a3c920420e62f2e8a0589cfd5bfb2e51be4ee8`;
- MIT license;
- blind extraction under the plan-supplied payload length and `k`;
- no ECC or Base/Detail semantics.

### B2

- blind 8×8 orthonormal DCT scalar-QIM;
- 32 frozen AC positions per block;
- exact 131,072-bit capacity for full raw secret;
- frozen delta candidates;
- up to four deterministic parity-preserving clean repair passes;
- clean-valid candidate selected by closest realized PSNR;
- external lineage pinned to `MasonEdgar/DCT-Image-Steganography` commit `20da3e1e4d6b48dbcbe241c776ee156995bb65fe`;
- MIT license;
- no ECC or Base/Detail semantics.

### Isolated fixture evidence

On the deterministic synthetic fixture declared in `BASELINE_CLEAN_FIXTURE_EVIDENCE.json`:

- B1: `k=3`, PSNR `45.68843569179694 dB`, clean bit errors `0`;
- B2: `delta=3.0`, one repair pass, PSNR `44.93491655128481 dB`, clean bit errors `0`.

This evidence is an engineering fixture, not a scientific result. Repository CI and target-server dry run remain required.

### Freeze authority

- `docs/5j/baselines/B1_CONTRACT.json`
- `docs/5j/baselines/B2_CONTRACT.json`
- `configs/5j/baseline_registry_v1.json`
- `docs/5j/baselines/BASELINE_CODE_FREEZE.json`
- `scripts/5j/validate_baseline_freeze.py`

Any frozen-byte or algorithm-contract change requires a new baseline freeze ID, rebuilt execution plan, and new run ID.

## Runtime completed

- `src/ctsteg/digital_ad/runtime_baseline_worker_5j.py`
- `scripts/5j/run_task.py`
- `src/ctsteg/digital_ad/runtime_dispatch_5j.py`
- `scripts/5j/dispatch_research.py`

The dispatcher is deliberately simple:

```text
all embeddings
→ local hash/schema validation
→ clean embedding acceptance
→ all evaluations
→ run_complete_local
```

It reuses `DurableTaskRunner`, `RunLock`, `ContentStore`, spawn-based process workers, cache hits, event logs, and `state.json`. The default is 16 single-threaded workers with resource bounds. No backup state participates in scheduling.

## Data preparation completed as tooling

- `data-manifests/5j/candidate_pairs.template.csv`
- `scripts/5j/freeze_data_manifests.py`
- `tests/test_5j_data_freeze.py`

At least 54 real candidate pairs are required. The outcome-blind selection is SHA-256 based:

- first 2: calibration;
- next 2: engineering dry run;
- next 50: main;
- 10 independently ranked main pairs: sweep subset.

The freezer verifies rights metadata, image bytes, exact dimensions, grayscale mode, uniqueness, and split disjointness. It does not download or invent data or rights.

## Stability tooling completed

- `scripts/5j/build_stability_profile.py`
- `tests/test_5j_stability_builder.py`

The profile uses calibration covers only and records input, manifest, config, transform, and profile identities.

## Analysis and reporting completed

- `src/ctsteg/digital_ad/analysis_5j.py`
- `scripts/5j/build_analysis.py`
- `scripts/5j/build_tables.py`
- `scripts/5j/build_figures.py`
- `tests/test_5j_analysis.py`
- `tests/test_5j_reporting.py`

Implemented outputs:

- raw JSONL and CSV;
- optional Parquet when `pyarrow` is installed;
- pair×method×condition aggregation;
- one overall row per pair and method;
- method summaries with mean, median, standard deviation, IQR, and range;
- C3–C0, C3–C3_NP, C3–B1, and C3–B2 paired comparisons;
- absolute and relative effects;
- direction counts;
- pair-cluster bootstrap 95% confidence intervals;
- paired Wilcoxon p-values;
- Holm correction;
- explicit operational-failure sensitivity analysis;
- failure-stage distributions;
- CSV, Markdown, and LaTeX tables;
- PNG and PDF figures.

## Final-only archive completed

- `scripts/5j/build_final_archive.py`
- `scripts/5j/verify_final_archive.py`
- `tests/test_5j_final_archive.py`

The archive is deterministic under frozen `SOURCE_DATE_EPOCH`, sorted paths, zero tar metadata, and gzip `mtime=0`. It contains an internal SHA-256 inventory and external sidecar. The verifier checks archive SHA, inventory identity, member set, size, and every file hash. Plaintext secret names/headers and common GitHub token patterns are rejected.

## CI workflows added

- `.github/workflows/5j-baselines.yml`
- `.github/workflows/5j-data-preparation.yml`
- `.github/workflows/5j-analysis.yml`
- `.github/workflows/5j-final-archive.yml`

At checkpoint time, GitHub returned no workflow runs or commit statuses for the latest head. Therefore none of the new workflows are claimed green.

## Remaining blockers requiring real external state

1. Provide at least 54 real, preprocessed, rights-documented cover-secret pairs.
2. Run `freeze_data_manifests.py` and validate all four manifests.
3. Run the real PDFB stability calibration on the target environment.
4. Freeze runtime bindings and rebuild/finalize the execution plan after the final source commit.
5. Obtain observable green CI or fix concrete workflow failures.
6. Upgrade/connect the 32-CPU, 64-GiB server and run the 16-worker benchmark.
7. Run the two-pair engineering dry run across all seven methods.
8. Execute the main study and sweeps.
9. Generate frozen analysis, tables, and figures.
10. Revise manuscript narrative based only on frozen results and compile PDFs.
11. Build, upload, and independently verify one final archive.

## Immediate continuation order

```text
real candidate-pair catalog
→ deterministic data freeze
→ real stability profile
→ final source/runtime/plan freeze
→ CI and server dry run
→ full numerical execution
→ analysis/tables/figures
→ result-driven manuscript revision
→ one final verified archive
```
