# FINAL-5J-v1 Data and Baseline Contract

Status: **implementation contract; scientific inputs not yet frozen**

This document defines what must be known, recorded, and validated before any 5J scientific row is authorized. It is intentionally fail-closed: missing provenance, rights, hashes, baseline identity, or harmonization evidence blocks the main run.

## 1. Dataset partitions

Four pair sets are required:

| Set | Purpose | Size rule | Relationship |
|---|---|---:|---|
| `calibration` | engineering/calibration only | at least 2 | disjoint from all other sets |
| `dry_run` | end-to-end infrastructure tests | at least 2 | disjoint from calibration and main |
| `main` | preregistered scientific experiment | exactly 50 | frozen before result inspection |
| `sweep` | payload and PSNR sweeps | exactly 10 | deterministic subset of `main` |

A pair is identified by `pair_id`. A source image may not silently appear in multiple roles under different pair IDs. Validators must therefore inspect both pair IDs and content SHA-256 values.

## 2. Required manifest columns

5J continues to use UTF-8 CSV pair manifests so the existing `ctsteg.manifest` reader remains the execution boundary. Every final 5J manifest must contain these columns:

```text
pair_id
split
cover
secret
cover_sha256
secret_sha256
cover_source
secret_source
cover_rights_status
secret_rights_status
cover_license
secret_license
cover_width
cover_height
secret_width
secret_height
cover_mode
secret_mode
preprocessing_id
redistribution_allowed
private_archive_object_id
notes
```

The execution paths `cover` and `secret` may refer to restored private assets. GitHub does not need to contain redistributable image bytes, but it must contain enough metadata, hashes, and recovery references to prove which exact bytes were used.

## 3. Rights and redistribution

Allowed rights-status values are:

- `public_domain`;
- `redistribution_permitted`;
- `research_use_only`;
- `private_permission`;
- `metadata_only`.

`redistribution_allowed` is an explicit boolean and must not be inferred from the source name. If redistribution is not allowed, GitHub stores only metadata and hashes plus the identifier of a client-side encrypted private archive. Decryption material remains outside GitHub.

Unknown or undocumented rights block scientific freeze.

## 4. Image and preprocessing identity

For every cover and secret, record:

- SHA-256 of the exact input bytes;
- source and rights status;
- dimensions and mode before execution;
- deterministic `preprocessing_id`;
- exact restored path at execution time;
- private archive object identifier when bytes are not public.

Preprocessing must be implemented as versioned code/configuration. Manual image edits are prohibited unless the transformed output is itself hashed, archived, and listed as the exact experiment input.

## 5. Freeze procedure

The data freeze is valid only when:

1. all four final manifests exist;
2. the main manifest has exactly 50 unique pairs;
3. the sweep manifest has exactly 10 pairs and is a subset of main;
4. calibration and dry-run assets are disjoint from main by pair ID and content hash;
5. all hashes, dimensions, modes, paths, and rights fields validate;
6. all required private assets have a verified off-server encrypted backup;
7. the manifests and their aggregate SHA-256 values are committed;
8. no scientific result has been inspected before the freeze commit.

Changing any main or sweep pair after freeze requires a protocol revision and new run ID.

## 6. Baseline slots

The main matrix reserves two external methods: `B1` and `B2`. A slot is not a method identity. Each slot remains disabled until its contract records:

- paper citation and implementation repository;
- exact source commit or release tag;
- software license and compatibility decision;
- original author execution contract;
- all local adaptations and their scientific consequences;
- input dimensions, color mode, payload definition, and overhead;
- distortion measurement boundary and PSNR control;
- extraction mode: blind, semi-blind, or non-blind;
- attack mapping and deterministic/random behavior;
- success, BER, reconstruction, runtime, and memory definitions;
- clean round-trip evidence;
- unsupported metrics represented as `not_applicable`;
- signed approval state and reviewer/date metadata.

## 7. Harmonization rules

Common comparisons require the same exact pair bytes, raw secret information, declared payload accounting, cover–stego quality boundary, attacks, realizations, quantization boundary, and metric implementation wherever technically meaningful.

Adaptations must be classified:

- `wrapper_only`: invocation or I/O conversion without changing the algorithm;
- `contract_harmonization`: a declared change required for common payload/quality/metrics;
- `algorithmic_change`: a substantive change; it must not be described as author-equivalent.

A baseline is never assigned zero for a semantically unavailable Base/Detail metric. The value is `not_applicable`.

## 8. Baseline acceptance gate

A slot is `approved` only if:

- source identity and license are fixed;
- adapter and dependency inventory are committed;
- clean round-trip behavior is tested under a preregistered rule;
- quality and payload accounting are auditable;
- deterministic object identity includes the baseline commit and adapter fingerprint;
- harmonization limitations are written before main results;
- the machine-readable registry marks the slot approved.

An irreproducible or scientifically failing baseline may be retained only if the failure rule was preregistered and the failed evidence remains archived. A candidate may not be tuned repeatedly against the final 50 pairs.

## 9. Machine-readable files

- `configs/5j/data_registry_v1.json`
- `configs/5j/baseline_registry_v1.json`
- `configs/5j/seeds.lock.json`
- `schemas/5j/pair_manifest.schema.json`
- `schemas/5j/baseline_contract.schema.json`
- `scripts/5j/validate_inputs.py`

Template CSVs are stored under `data-manifests/5j/`. Template presence is implementation readiness, not scientific readiness.

## 10. Current authorization state

At the creation of this contract:

- the 50-pair manifest is not frozen;
- the 10-pair sweep subset is not frozen;
- B1 and B2 are not selected;
- no scientific execution is authorized.

The validator must report these as explicit blockers while still permitting CI to verify that the scaffolding itself is internally valid.