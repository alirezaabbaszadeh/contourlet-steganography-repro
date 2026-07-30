# Final PDFB v2 run record — 2026-07-30

## Identity and claim boundary

- Run ID: `f7acf6d9d31dd66cddf1`
- Numerical execution commit: `7ff0c5abf4511c803a935645dcc2c3ed012f05e9`
- Final reporting/resume commit: `c564d209844a9dfdb74bf9031fa1ddf3af72cad4`
- Branch: `agent/runtime-resume-gate`
- Transform interpretation:
  `octave_pdfb_9_7_pkva_nlev_2222_p3p4_range_v2`
- Scientific status:
  `final_pdfb_range_multiscale_coordinates_not_author_equivalent`

The reporting commit changes typed Parquet serialization and metric-field
projection only. The numerical source fingerprint and all 88 immutable
content-object IDs are unchanged. The final resume reused every numerical
object and did not recompute an embedding or channel evaluation.

## Locked execution result

- Status: `complete`
- Core embeddings: 16/16 complete, 0 operational failures
- Mandatory evaluation rows: 64/64
- Conditional hard-check rows: 24/24
- Total evaluation rows: 88/88
- Triggered hard-check families: Gaussian, JPEG, and salt-and-pepper
- Resume cache hits: 16 embeddings, 48 core channels, 24 hard checks
- Parquet status: written and required

All 16 clean cases decoded successfully. Their effective unrecovered bit rate
was zero. Under every tested medium and hard channel, the effective
unrecovered bit rate was one for all tested methods and traceability pairs.
Consequently, the locked data show no C0-to-C3 robustness advantage under
these channel conditions. This negative result must not be expanded into an
untested universal claim.

## Runtime gate

- Gate ID: `20260730T134046Z-98265862`
- Gate report SHA-256:
  `b03f17eaf0389c89e984cdea3614bf390eb7e23b86b7405163083c4caf138f7d`
- Runtime fingerprint:
  `b9281266867c9ed2cece239a6951cef3b7b6884c1b286781c2c5ef6d4c4a66c1`
- Real `SIGKILL`, unchanged-object reuse, archive checksums, and all
  machine-checkable gate conditions passed.

## Final archive

- Filename:
  `CTSteg-final-PDFB-v2-f7acf6d9.tar.gz`
- SHA-256:
  `5a367ddb07c3df88c2a3ea7ec38187d1ea195e898a61baaa8e733d6dd347b663`
- Size: 23,059,034 bytes
- Immutable objects: 88
- Files checked: 1,582
- Archive validation: passed
- Bundle material SHA-256:
  `86f889f4bd334ba51d3112a8c8b26ba16ff7f47bdd90b9dd2fac2c0a75b0c100`

The verified archive was copied off CPU8 before shutdown. It contains
image-derived research artifacts and must not be attached to a public release
until the dataset redistribution decision is reviewed.

## Private deletion-safe reproduction capsule

- Filename: `CTSteg-reproduction-capsule-20260730.tar.gz`
- SHA-256:
  `d88a022b2cfca54ab2c9572bd6d0a442a61f169d97c4e27ffe59ef0adccd431d`
- Size: 32,559,533 bytes
- Integrity manifest: 351 regular files
- Independently matched against CPU8:
  27 input files, 72 toolbox files, and 242 evidence files, with zero missing
  or mismatched SHA-256 values.

The private capsule additionally contains the exact raw core/calibration
inputs, rights metadata, transform-bound stability profile, complete locked
Contourlet tree, environment/package inventories, offline Git bundle, restore
instructions, and the validated 88-object result archive. Its hash is tracked
here, but the capsule itself is not published because it contains material
that requires a separate redistribution decision.

## Report hashes

| Artifact | SHA-256 |
|---|---|
| `run_summary.json` | `7ff156cf909fbb4957c974cb5b85d9e22e49e731bc7ecbd5698db7a3dc93f4ff` |
| `evaluations.csv` | `6ca74fdf36c0c33e0e84c902480074aff3697fa31086c02bb9e4cafa59c7e689` |
| `evaluations.json` | `7605e975d13d415d9682383467a028bcb353bed927fd3df53eb599444ff57aa8` |
| `evaluations.jsonl` | `d511cc8fd2a1d682cb3331e84a524cc7ff00f6ed014d6cbfa151aa58af42dad2` |
| `evaluations.parquet` | `ffb46ce3d9db4b957428afe3f8b0131e75a69f49976dd73fba2140d65a533d9d` |
| `summary.json` | `9ffa113bbf5ee8a75d9408e33af492f8a051071e11b65cd208b6feaa6b0dfb03` |
| `contrasts.json` | `e737ab5e22f44ba6ceb899de7c5926c2bab8bcfe8599f065a0f9edfe04419fcd` |
