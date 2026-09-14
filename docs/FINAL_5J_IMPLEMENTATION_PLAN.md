# Final 5J Implementation, Execution, Analysis, and Backup Plan

Status: **author-approved planning baseline**  
Plan identifier: `FINAL-5J-v1`  
Target repository: `alirezaabbaszadeh/contourlet-steganography-repro`  
Planning branch: `agent/runtime-resume-gate`  
Supersedes: informal chat-only descriptions of options 5J and failure-severity analysis

## خلاصه فارسی

این سند مرجع اصلی توسعه و اجرای نسخه نهایی 5J است. اگر گفتگو یا سرور از دست برود، ادامه کار باید از این سند، Issue اجرایی مرتبط، commitهای ثبت‌شده، manifestها و بسته‌های پشتیبان انجام شود.

اصل غیرقابل مذاکره این برنامه:

> هیچ داده، نتیجه، cache معتبر، گزارش، log، manifest، کد، تنظیمات یا artifact علمی نباید تنها روی سرور باقی بماند.

هر شیء کامل‌شده باید پیش از آن‌که «قابل اتکا» یا «تکمیل‌شده» اعلام شود، hash شود، در manifest ثبت شود و یک نسخه تأییدشده خارج از سرور داشته باشد.

با وجود این، **کلید خصوصی، token، password، license key و recovery key هرگز به‌صورت plaintext در GitHub ذخیره نمی‌شوند**. GitHub فقط می‌تواند ciphertext، public key، fingerprint، metadata بازیابی و GitHub Actions/Environment Secrets را نگهداری کند. قرار دادن هم‌زمان ciphertext و کلید رمزگشایی در یک حساب GitHub، پشتیبان امن محسوب نمی‌شود.

---

## 1. Scientific objective

The final 5J study must answer five questions under one harmonized contract:

1. Does the proposed hierarchical method improve complete recovery relative to C0 and external baselines?
2. Does it preserve a **valid Base-only reconstruction** after complete recovery fails?
3. Which component causes the effect: adaptive allocation, unequal protection, Base-first placement, or their combination?
4. When methods fail, **how and by how much** do they fail rather than merely receiving the same binary failure label?
5. How do payload, cover-stego quality, attack severity, runtime, and memory trade off against recovery?

The previous locked run remains immutable historical evidence. 5J is a new protocol version, new run identity, new result namespace, and new manuscript claim set. No 5J result may overwrite or reinterpret the previous 88-object archive.

---

## 2. Frozen 5J scope

### 2.1 Dataset size

- 50 preregistered cover-secret pairs.
- Pair selection must be deterministic and recorded before scientific results are inspected.
- Calibration, engineering dry-run, and final-study pairs must be disjoint.
- Every input file must have source, rights status, size, dimensions, SHA-256, preprocessing record, and role in a machine-readable manifest.

### 2.2 Methods

The main study contains seven methods:

| ID | Method |
|---|---|
| `C0` | fixed allocation, symmetric protection, non-prioritized placement |
| `C1` | adaptive allocation, symmetric protection, non-prioritized placement |
| `C2` | fixed allocation, unequal Base/Detail protection, non-prioritized placement |
| `C3_NP` | adaptive allocation plus unequal protection, **without Base-first placement** |
| `C3` | full proposed method: adaptive allocation, unequal protection, Base-first placement |
| `B1` | first external baseline under the harmonized contract |
| `B2` | second external baseline under the harmonized contract |

`B1` and `B2` are not frozen until code availability, license, reproducibility, payload contract, distortion control, extraction requirements, and attack compatibility are reviewed. Their final identities and exact commits must be recorded in a baseline contract before the main run.

### 2.3 Partial-recovery protocol

The payload format must support independent integrity decisions:

- independent Base CRC/integrity field;
- independent Detail CRC/integrity field;
- complete payload integrity;
- deterministic Base-only reconstruction;
- explicit output states:
  - `complete_valid_recovery`;
  - `valid_base_only_recovery`;
  - `header_valid_no_valid_layer`;
  - `header_failure`;
  - `extraction_failure`;
  - `operational_failure`.

A diagnostic image produced without valid Base integrity must be labelled `diagnostic_unverified` and must never be counted as valid recovery.

### 2.4 Main attack matrix

Each main-study embedding is evaluated under 22 channel instances:

| Family | Conditions | Realizations | Evaluations per embedding |
|---|---:|---:|---:|
| Clean | 1 | deterministic | 1 |
| JPEG | Q=90, 70, 50 | deterministic | 3 |
| Gaussian | variance=5, 10, 15 | 3 preregistered realizations each | 9 |
| Salt-and-pepper | density=0.01, 0.03, 0.05 | 3 preregistered realizations each | 9 |
| **Total** |  |  | **22** |

Random seeds are protocol inputs. They must be frozen before result inspection and may not be expanded after observing outcomes.

### 2.5 Main-study count

- 50 pairs × 7 methods = **350 embeddings**.
- 350 embeddings × 22 channel instances = **7,700 evaluations**.

### 2.6 Payload sweep

Methods: `C0`, `C3_NP`, `C3`  
Pairs: 10 preregistered sweep pairs  
Payload levels: 25%, 50%, 75%, 100%  
Conditions: Clean, JPEG Q=70, Gaussian variance=10, salt-and-pepper density=0.03

The 100% operating point is already represented in the main matrix. Therefore the incremental sweep contains:

- 10 × 3 methods × 3 new payload levels = **90 additional embeddings**;
- 90 × 4 conditions = **360 additional evaluations**.

### 2.7 PSNR sweep

Methods: `C0`, `C3_NP`, `C3`  
Pairs: the same 10 preregistered sweep pairs  
Target PSNR: 40.0, 42.5, 45.0, 47.5 dB  
Conditions: Clean, JPEG Q=70, Gaussian variance=10, salt-and-pepper density=0.03

The 45 dB operating point is already represented in the main matrix. Therefore the incremental sweep contains:

- 10 × 3 methods × 3 new PSNR levels = **90 additional embeddings**;
- 90 × 4 conditions = **360 additional evaluations**.

### 2.8 Final planned size

| Component | Embeddings | Evaluations |
|---|---:|---:|
| Main matrix | 350 | 7,700 |
| Payload sweep | 90 | 360 |
| PSNR sweep | 90 | 360 |
| **Total** | **530** | **8,420** |

Any expansion requires a new protocol revision before results are inspected. Outcome-driven expansion is prohibited.

---

## 3. Comparative failure-severity analysis

Binary success/failure is insufficient. The 5J result schema must quantify how close each failed stream was to useful or complete recovery.

### 3.1 Failure stage

Each evaluation receives one primary stage:

| Code | Meaning |
|---|---|
| `S0_COMPLETE` | complete payload valid |
| `S1_BASE_ONLY` | Base valid, Detail invalid |
| `S2_HEADER_VALID_PARTIAL` | header valid, no layer passes integrity, partial data available |
| `S3_PAYLOAD_ECC_FAILURE` | payload codewords exceed correction capability |
| `S4_HEADER_FAILURE` | header cannot be validated |
| `S5_EXTRACTION_TRANSFORM_FAILURE` | extraction or transform boundary failure |
| `S6_OPERATIONAL_FAILURE` | software, environment, resource, or infrastructure failure |

Scientific failures and operational failures must never be pooled.

### 3.2 ECC overload

For codeword `i`, record observed symbol errors `e_i`, correction radius `t_i`, and overload:

```text
O_i = max(0, e_i - t_i)
```

Required summaries, separately for Base and Detail:

- successful codeword count;
- failed codeword count;
- total corrected symbols;
- mean, median, maximum, and distribution of `O_i`;
- fraction of codewords at or below radius;
- distance of the worst required codeword beyond radius.

### 3.3 Recovery fractions

Required metrics:

- complete recovery indicator;
- valid Base-only indicator;
- correctly recovered protected-payload fraction;
- correctly recovered raw-secret fraction;
- Base bit recovery fraction;
- Detail bit recovery fraction;
- Base BER and Detail BER;
- unknown-bit fraction;
- header known/correct fraction;
- reconstruction PSNR, SSIM, MSE, and NCC where meaningful.

For external baselines without semantic Base/Detail layers, layer-specific fields must be `not_applicable`, not zero.

### 3.4 Boundary curves

For every method and attack family, generate severity-dependent curves for:

- complete recovery rate;
- Base-only recovery rate;
- recovered payload fraction;
- Base and Detail BER;
- failure-stage distribution;
- ECC overload;
- reconstructed-secret PSNR/SSIM.

The report must distinguish:

- a method that fails slightly beyond the correction radius;
- a method that loses the header;
- a method that preserves valid Base content;
- a catastrophic extraction or operational failure.

---

## 4. Harmonized baseline contract

Before B1 or B2 enters the run, create a signed-off contract recording:

- paper and repository citation;
- source commit/tag and license;
- original and adapted execution path;
- cover and secret requirements;
- payload definition, including metadata/ECC overhead;
- distortion constraint and measurement boundary;
- extraction mode: blind, semi-blind, or non-blind;
- color/grayscale and quantization behavior;
- attack implementation and parameter mapping;
- success, BER, and reconstruction definitions;
- any adaptation that changes author-equivalent behavior.

The common comparison fields are:

- cover-stego PSNR/SSIM;
- raw payload and protected overhead;
- complete recovery rate;
- recovered secret fraction and BER;
- reconstructed-secret PSNR/SSIM;
- failure threshold and failure severity;
- runtime and peak memory.

No baseline is penalized for lacking Base/Detail semantics.

---

## 5. Statistical analysis plan

The Statistical Analysis Plan must be committed and frozen before the final run.

### 5.1 Experimental unit

The primary experimental unit is the **image pair**. Attack realizations are repeated observations within a pair and must not be treated as independent image samples.

### 5.2 Primary endpoints

1. Complete Recovery Rate.
2. Valid Base-only Recovery Rate.
3. Paired C3 minus C0 effect.
4. Paired C3 minus C3_NP effect, isolating Base-first placement.
5. Paired C3 minus B1 and C3 minus B2 effects on common metrics.
6. Comparative failure-severity gap among failed evaluations.

### 5.3 Secondary endpoints

- Base/Detail BER and recovery fractions;
- recovered payload fraction;
- ECC overload and failed-codeword counts;
- reconstruction PSNR/SSIM/NCC;
- cover-stego quality;
- runtime, memory, and throughput;
- payload and PSNR sweep curves;
- operational failure rate.

### 5.4 Required reporting

- raw rows;
- paired differences;
- mean, median, standard deviation, IQR, range, and direction count;
- pair-cluster bootstrap confidence intervals;
- paired tests appropriate to endpoint type;
- Holm correction for the preregistered primary comparison family;
- effect sizes, not only p-values;
- all failures and missing cells with reasons;
- sensitivity analysis excluding only documented operational failures;
- no deletion of scientific failures.

### 5.5 Prohibited practices

- adding pairs, methods, seeds, or attack levels after observing outcomes;
- selecting only favorable attacks or images;
- replacing failed rows without preserving the failed object;
- treating attack realizations as independent image pairs;
- hand-copying final table values into LaTeX;
- changing primary endpoints after unblinding.

---

## 6. Required repository implementation

The following structure should be created during implementation:

```text
docs/5j/
  PROTOCOL.md
  STATISTICAL_ANALYSIS_PLAN.md
  FAILURE_SEVERITY_SPEC.md
  DATA_AND_BASELINE_CONTRACT.md
  SECURITY_BACKUP_POLICY.md
  SERVER_EXECUTION_RUNBOOK.md
  RESULT_SCHEMA.md
  MANUSCRIPT_REPORTING_PLAN.md

configs/5j/
  format_v2_layer_integrity.toml
  attacks_v1.toml
  main_50_pairs.toml
  payload_sweep.toml
  psnr_sweep.toml
  seeds.lock.json

schemas/5j/
  pair_manifest.schema.json
  embedding.schema.json
  evaluation.schema.json
  backup_ledger.schema.json
  run_summary.schema.json

scripts/5j/
  validate_protocol.py
  validate_manifests.py
  validate_baselines.py
  plan_run.py
  run_research.py
  sync_completed_objects.py
  verify_remote_backup.py
  evacuate_server.py
  build_analysis.py
  build_tables.py
  build_figures.py
  build_manuscript_package.py

.github/workflows/
  5j-ci.yml
  5j-protocol-validation.yml
  5j-backup-ledger-validation.yml
  5j-manuscript.yml
```

All schemas, configs, tables, and figures must be deterministic and versioned.

---

## 7. Development phases and acceptance gates

### Phase 0 — governance and security

Deliverables:

- this plan;
- security and backup policy;
- secret inventory template containing names and fingerprints only;
- incident response and key-rotation procedure;
- repository and artifact visibility review.

Gate: no implementation begins until plaintext-secret exclusion is accepted.

### Phase 1 — protocol and schemas

Deliverables:

- final method definitions;
- final count of 530 embeddings and 8,420 evaluations;
- pair manifest schema;
- attack and seed locks;
- failure-severity schema;
- Statistical Analysis Plan;
- baseline acceptance checklist.

Gate: a validator reproduces the exact planned counts and rejects expansion.

### Phase 2 — layer-specific integrity

Deliverables:

- Base and Detail integrity fields;
- deterministic complete/Base-only/no-valid-output states;
- versioned decoder behavior;
- bit-exact unit and integration tests;
- backward reader for the previous format where practical, without mixing results.

Gate: corruption tests prove that Base-only validity cannot be falsely declared.

### Phase 3 — C3_NP ablation

Deliverables:

- explicit placement switch;
- C3_NP method identity;
- tests proving C3_NP differs from C3 only in Base-first placement;
- coefficient-map and method fingerprints.

Gate: automated structural diff confirms the intended single-factor distinction.

### Phase 4 — external baselines

Deliverables:

- B1/B2 adapters;
- source/license records;
- harmonization report;
- common metrics adapter;
- unsupported metric handling as `not_applicable`.

Gate: each baseline passes clean round-trip or retains a documented scientific failure under a preregistered rule.

### Phase 5 — result and failure schemas

Deliverables:

- typed JSON, JSONL, CSV, and Parquet outputs;
- codeword-level error and overload records;
- failure-stage records;
- layer metrics;
- runtime and memory telemetry;
- backup ledger entries.

Gate: synthetic fixtures cover every success and failure class.

### Phase 6 — dry run

Use at least two engineering-only pairs not present in the final 50.

Test:

- all seven methods;
- all 22 channel instances;
- Base-only validity;
- payload and PSNR sweep paths;
- interruption and resume;
- backup before completion acknowledgement;
- report generation and manuscript compilation.

Gate: no unbacked completed object remains after forced interruption or reboot.

### Phase 7 — locked pilot

Use five preregistered final pairs to expose operational defects only.

Rules:

- scientific parameters remain frozen;
- bugs require a documented issue, failing test, fix commit, and protocol impact review;
- pilot rows are either retained under the final code identity or the entire final run receives a new run identity.

Gate: all backup, schema, and analysis checks pass.

### Phase 8 — main execution

Order:

1. Generate and back up 350 main embeddings.
2. Evaluate and back up 7,700 main rows.
3. Generate/back up 90 payload-sweep embeddings and 360 rows.
4. Generate/back up 90 PSNR-sweep embeddings and 360 rows.
5. Produce final reports and validate all counts.

Gate: 530 embeddings and 8,420 evaluations are present, valid, backed up, and accounted for.

### Phase 9 — analysis and manuscript

Deliverables:

- preregistered statistical outputs;
- failure-severity comparison;
- tables and figures generated from frozen reports;
- five-section manuscript structure;
- expanded Related Work and baseline table;
- ablation section;
- Results and Discussion combined where required;
- honest limitations and protocol-difference notes;
- main and supplementary PDFs;
- claim-evidence matrix linking every statement to result rows.

Gate: no numerical value is hand-entered without a machine-readable source link.

---

## 8. No-server-only-data invariant

### 8.1 Core rule

The server is disposable compute, not the authoritative archive.

An object is considered `committed_complete` only after all of the following succeed:

1. local atomic write;
2. local validation;
3. SHA-256 and size recorded;
4. backup upload completed;
5. remote object/asset identity recorded;
6. remote download or API verification completed;
7. backup ledger committed outside the server.

Until then, the object state is `complete_unbacked` and the scheduler must not count it as durable progress.

### 8.2 Backup ledger

Every object must record:

- run ID and protocol version;
- object ID and type;
- local relative path;
- SHA-256 and byte size;
- parent/input object IDs;
- creation commit and runtime fingerprint;
- sensitivity/licensing class;
- encryption status and algorithm identifier;
- remote GitHub location or asset identifier;
- upload timestamp;
- verification timestamp and verifier result;
- supersession/tombstone status.

### 8.3 Data classes

| Class | Examples | GitHub storage rule |
|---|---|---|
| Public text/code | source, configs, schemas, manifests without restricted paths | normal repository commit |
| Public binary | redistributable figures, PDFs, small reports | repository or release asset |
| Large scientific artifact | embeddings, Parquet, logs, archives | content-addressed release assets or approved private artifact repository |
| Restricted/licensed input | non-redistributable images/toolbox | client-side encrypted archive in an approved private GitHub location; rights metadata in the public repo |
| Secret | private SSH keys, tokens, passwords, MATLAB credentials, recovery keys | **never plaintext in Git**; use GitHub encrypted secrets for runtime injection or client-side ciphertext with recovery key outside GitHub |

### 8.4 Shutdown and deletion gate

Before shutdown, reprovisioning, or deletion, `evacuate_server.py` must prove:

- zero `complete_unbacked` objects;
- zero unuploaded logs/manifests;
- final ledger is remotely committed;
- remote spot-check downloads match hashes;
- final server inventory and package state are archived;
- all temporary secret files are securely removed according to the documented platform procedure.

A server may be deleted only after an evacuation report passes.

---

## 9. Secret and key policy

### 9.1 Plaintext prohibition

Never commit or upload plaintext forms of:

- SSH private keys or PEM files;
- GitHub personal access tokens;
- cloud/API credentials;
- passwords;
- MATLAB license files, passwords, or activation keys;
- encryption recovery keys;
- private dataset credentials.

This applies even to a private repository. Git history, forks, caches, logs, and accidental visibility changes make plaintext secret storage unsafe.

### 9.2 Permitted GitHub records

GitHub may contain:

- public keys;
- cryptographic fingerprints;
- key names and purposes;
- creation, rotation, and revocation dates;
- encrypted ciphertext bundles;
- instructions for retrieving the separate recovery key;
- GitHub Actions/Environment secret names, never their values;
- evidence that a secret was tested, rotated, or revoked.

### 9.3 Encrypted backup design

If a private key must have a GitHub-hosted backup:

1. encrypt it **client-side** with a modern authenticated encryption tool;
2. upload only ciphertext to a dedicated private backup location;
3. store its SHA-256, encryption algorithm, recipient/key fingerprint, and restore test record in the ledger;
4. keep the decryption/recovery key outside GitHub in separate custody;
5. rotate the SSH key if plaintext exposure is suspected;
6. never print secret values in CI logs.

Storing ciphertext and its decryption key in the same GitHub account is prohibited because it eliminates the security benefit.

### 9.4 Current uploaded key

A private RSA key was supplied during planning as `/mnt/data/C8-privateKey.pem`. It must **not** be committed to this public repository. Before server use, register only its public-key fingerprint and purpose. After a secure access path is established, rotate or replace it if its handling history is uncertain.

---

## 10. Server-ready package

Before the server is powered on, GitHub must contain or reference:

- exact deployment commit;
- bootstrap scripts and pinned package versions;
- 5J configs and schema validators;
- final pair manifests or encrypted input bundle;
- toolbox inventory and encrypted/restorable package where licensing permits;
- B1/B2 source locks and adapters;
- attack seed lock;
- runtime gate configuration;
- backup destination and credential-name configuration;
- systemd services for compute, monitor, backup sync, and evacuation;
- test reports from CI;
- dry-run instructions;
- recovery instructions for a new chat or operator.

The server should require only:

1. host/IP and SSH user;
2. authorized public key;
3. runtime-injected secret values;
4. MATLAB license activation where required;
5. execution of the verified bootstrap command.

No scientific design decision should be made interactively on the server.

---

## 11. GitHub issue and commit discipline

Every implementation change must reference an issue. Recommended issue groups:

1. Protocol and analysis freeze.
2. Layer-specific integrity and format version.
3. C3_NP ablation.
4. Baseline B1.
5. Baseline B2.
6. Result/failure schema.
7. Backup ledger and remote verification.
8. Server bootstrap and resume.
9. Dry run and pilot.
10. Main execution.
11. Analysis, tables, figures, and manuscript.
12. Release, archival verification, and server evacuation.

Commit messages must identify the phase and whether the change affects scientific identity. Scientific changes after freeze require a protocol revision and new run ID.

---

## 12. Recovery instructions for a future chat

A future operator or chat should:

1. Open this file first.
2. Read the linked 5J tracking issue and unresolved tasks.
3. Inspect the current implementation branch and latest protocol commit.
4. Verify that no plaintext secret has been committed.
5. Confirm B1/B2 identities and the frozen 50-pair manifest.
6. Run protocol/schema/plan validators and confirm `530 embeddings / 8420 evaluations`.
7. Verify remote backup destinations and ledger access.
8. Run CI and dry-run gates before connecting to the production server.
9. Start the server only from an exact commit SHA.
10. Never mark server work complete until remote backup verification passes.

---

## 13. Definition of done

5J is complete only when:

- all 530 embeddings and 8,420 evaluations are present or explicitly accounted for;
- every scientific and operational failure is retained;
- every durable object has a verified off-server GitHub backup record;
- no plaintext secret exists in repository history or release assets;
- all primary and secondary analyses are generated from frozen machine-readable data;
- complete versus Base-only versus deeper failure is reported;
- C3 is compared with C0, C3_NP, B1, and B2 under the harmonized contract;
- payload/PSNR/severity trade-offs are reported;
- runtime and memory are reported;
- manuscript and supplement compile reproducibly;
- a final encrypted/private evidence archive, public release package, checksum inventory, and evacuation report exist;
- the server can be destroyed without losing any unique project information.

---

## 14. Immediate next actions

1. Create the 5J tracking issue with this plan as its authority.
2. Split the implementation into the issue groups listed above.
3. Add `docs/5j/SECURITY_BACKUP_POLICY.md` first.
4. Add protocol, result, and backup-ledger schemas.
5. Select and approve B1/B2 before implementing the final matrix.
6. Build layer-specific integrity and C3_NP.
7. Build remote backup verification before any production execution.
8. Prepare the server-ready release from an exact commit SHA.

No production 5J computation begins until phases 0–7 pass their gates.
