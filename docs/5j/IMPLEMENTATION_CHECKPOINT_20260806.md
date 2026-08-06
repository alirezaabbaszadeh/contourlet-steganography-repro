# FINAL-5J-v1 Implementation Checkpoint — 2026-08-06

This checkpoint is an append-only recovery note for future operators and ChatGPT conversations. The branch is `agent/runtime-resume-gate`; Issue #6 remains the work tracker. Do not infer CI success from file presence: workflow completion must be checked separately.

## Implemented governance and preregistration

- master implementation/backup plan;
- frozen 530-embedding / 8,420-evaluation protocol;
- Statistical Analysis Plan baseline;
- comparative S0–S6 failure-severity specification;
- security and remote-verified backup policy;
- machine-readable study plan, exact count validator, and deterministic plan summary.

## Implemented data and baseline gates

- pair provenance/rights/disjointness contract;
- calibration, dry-run, main-50, and sweep-10 manifest templates;
- data registry and pair-row schema;
- B1/B2 pending contract files, registry, and approval schema;
- exact 22-instance attack seed lock with pair-specific deterministic seed derivation;
- fail-closed input-readiness validator;
- production scientific run remains blocked until real manifests, rights, hashes, B1/B2 approvals, and backup prerequisites are complete.

## Implemented format-v2 and C3_NP core

- format version 2 reuses eight existing reserved header bytes for independent Base and Detail CRC32 fields;
- header size remains 127 raw / 255 RS-encoded bytes;
- full protected payload remains 222,360 bits at the 100% point;
- format-v1 C0–C3 identities and decoding remain separate and immutable;
- `C3_NP` is an additive method identity and is rejected under format v1;
- C3 and C3_NP share adaptive allocation, unequal protection, band weights, slot quotas, ordered coefficient map, and map fingerprint;
- their sole preregistered difference is Base-first versus alternating layer transport order;
- decoder reports complete validity, valid Base-only recovery, header-valid/no-valid-layer, and header failure;
- Base-only reconstruction is emitted only after independent Base CRC validation.

## Implemented progressive payload sweep definition

Payload fractions transmit the most significant information first:

| Fraction | Base bits/pixel | Detail bits/pixel | Reconstruction mask |
|---:|---:|---:|---:|
| 25% | 2 | 0 | `0xC0` |
| 50% | 4 | 0 | `0xF0` |
| 75% | 4 | 2 | `0xFC` |
| 100% | 4 | 4 | `0xFF` |

Implemented components include:

- generic 2/4-bit symbol packing and unpacking;
- progressive split/recombine/reference functions;
- deterministic dynamic RS profile registry;
- variable protected stream sizes declared and checked by the header;
- variable-size coefficient slot plans;
- payload fraction threaded through encoding, decoding, embedding, and extraction;
- Detail applicability is `not_applicable`, not zero, when Detail is absent.

Expected protected-bit totals:

| Raw fraction | C0/C1 | C2/C3_NP/C3 |
|---:|---:|---:|
| 25% | 57,120 | 69,360 |
| 50% | 112,200 | 134,640 |
| 75% | 167,280 | 179,520 |
| 100% | 222,360 | 222,360 |

Cross-method sweep reporting must disclose actual protected bits; nominal raw fraction alone is not a fair overhead comparison.

## Implemented comparative failure diagnostics

For internal methods, diagnostics now derive from the actual extracted stream and retain:

- per-codeword observed symbol errors;
- RS data/parity symbols and correction radius;
- `ecc_overload = max(0, observed_errors - correction_radius)`;
- decoder and padding status;
- corrected-symbol count;
- raw bit errors for available decoded chunks;
- correct, known, and unknown declared-payload fractions;
- header, Base, and Detail summaries;
- S0–S5 scientific failure-stage mapping.

Operational failures remain S6 and must be produced by the runner rather than mixed into scientific decode diagnostics.

## Implemented result and execution schemas

- typed embedding schema;
- typed evaluation schema;
- run-summary schema;
- deterministic expanded execution-plan schema and builder;
- synthetic expansion test proving 530 unique embedding tasks and 8,420 unique evaluation tasks;
- plan/run IDs are content-addressed;
- source, config, manifests, seed lock, baseline registry, method fingerprint, payload fraction, PSNR target, channel instance, and pair seed participate in identities.

## Implemented remote backup lifecycle

- typed backup-ledger schema;
- deterministic append-only tar bundles with internal manifests;
- SHA-256 for every object and bundle;
- filesystem and GitHub Release backends;
- upload followed by download and content verification before `committed_complete`;
- periodic re-verification revokes stale completion on mismatch;
- plaintext secret objects are rejected;
- secret material must be client-side encrypted before bundling;
- server evacuation scan blocks on any untracked file, unuploaded log/manifest, hash mismatch, incomplete bundle, unresolved secret file, or unique server-only information.

GitHub Release bundling is required because a single release cannot hold one asset per scientific object at 5J scale. Recovery keys remain outside the GitHub account.

## Added tests/workflows

Tests have been added for:

- format-v1 compatibility and format-v2 integrity;
- false Base-only validity prevention;
- C3/C3_NP single-factor isolation;
- progressive payload packing, profiles, protected bits, and clean declared-payload decoding;
- comparative failure severity for clean, correctable, Base-only, header-failure, and absent-Detail cases;
- backup upload/restore/verification, plaintext-secret rejection, tamper revocation, and evacuation blocking;
- deterministic 530/8,420 task expansion.

Workflows exist for protocol, input readiness, format-v2 core, execution planning, and backup-ledger validation. At this checkpoint, CI conclusions must still be verified in GitHub Actions; prior setup failures included GitHub service unavailability and must not be misreported as code failures or successes.

## Remaining critical path

1. obtain green CI or fix concrete code failures;
2. add compatibility fallback/tests for direct extraction callers where needed;
3. select, license-review, harmonize, implement, and approve B1/B2;
4. freeze actual calibration/dry-run/main-50/sweep-10 manifests and encrypted private input archive;
5. implement the dedicated 5J runner consuming only the frozen expanded execution plan;
6. implement typed object serialization and normalized codeword-diagnostic child objects;
7. integrate automatic backup acknowledgement into runner completion;
8. add external-custody evidence registration for secrets that must never enter bundles;
9. execute synthetic and engineering dry runs, including SIGKILL/resume and remote restore;
10. run the locked five-pair operational pilot;
11. only then authorize the 50-pair main study.

## Non-negotiable rule

No scientific task is complete until its canonical object and required evidence are remotely backed up, re-downloaded or otherwise independently verified, and recorded as `committed_complete`. No plaintext private key, token, password, MATLAB credential, license key, or recovery key may enter Git history, Actions logs, release assets, or backup bundles.