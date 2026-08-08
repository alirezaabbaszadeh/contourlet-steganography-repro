# FINAL-5J-v1 Protocol

Status: implementation baseline  
Authority: `docs/FINAL_5J_IMPLEMENTATION_PLAN.md`

## 1. Study identity

5J is a new scientific protocol, run namespace, result archive, and manuscript claim set. It does not overwrite, merge into, or reinterpret the frozen 88-evaluation run.

Every 5J object identity must include the protocol identifier, format version, source commit, transform fingerprint, method identity, pair hashes, operating point, and—where applicable—channel realization seed.

## 2. Scientific questions

The study tests whether hierarchical payload organization and unequal protection:

1. improve complete recovery under a harmonized contract;
2. retain a valid Base-only reconstruction after complete recovery fails;
3. provide benefits attributable to adaptive allocation, unequal protection, Base-first placement, or their combination;
4. reduce failure severity when binary recovery still fails;
5. change payload–quality–robustness and runtime trade-offs.

## 3. Experimental units and data partitions

The primary experimental unit is an image pair. The final study contains exactly 50 preregistered cover–secret pairs.

Required disjoint partitions:

- calibration inputs;
- engineering dry-run inputs;
- 50 final-study pairs;
- 10 preregistered sweep pairs selected from the final 50.

All inputs require a machine-readable provenance and rights record plus SHA-256 identities. Pair selection and preprocessing must be frozen before scientific outputs are inspected.

## 4. Methods

The main matrix contains exactly seven methods:

| ID | Required distinction |
|---|---|
| `C0` | fixed allocation, symmetric protection, non-prioritized placement |
| `C1` | adaptive allocation, symmetric protection, non-prioritized placement |
| `C2` | fixed allocation, unequal protection, non-prioritized placement |
| `C3_NP` | adaptive allocation and unequal protection without Base-first placement |
| `C3` | adaptive allocation, unequal protection, Base-first placement |
| `B1` | first approved harmonized external baseline |
| `B2` | second approved harmonized external baseline |

`C3_NP` and `C3` must differ only in placement priority. B1 and B2 remain blocked until their source commit, license, adaptation, extraction mode, payload accounting, distortion boundary, and common metrics are signed off.

## 5. Layer-integrity format

The new payload format must provide:

- versioned header;
- independent Base integrity;
- independent Detail integrity;
- complete-payload integrity;
- deterministic Base-only reconstruction;
- explicit decoder states.

Required states:

- `complete_valid_recovery`;
- `valid_base_only_recovery`;
- `header_valid_no_valid_layer`;
- `header_failure`;
- `extraction_failure`;
- `operational_failure`.

An output without valid Base integrity may be stored only as `diagnostic_unverified` and may not count as recovery.

## 6. Main channel matrix

Every main embedding is evaluated under exactly 22 channel instances:

- Clean: one deterministic instance;
- JPEG: Q=90, Q=70, Q=50;
- Gaussian: variance 5, 10, 15 with three preregistered realizations at each level;
- Salt-and-pepper: density 0.01, 0.03, 0.05 with three preregistered realizations at each level.

Random seeds are protocol inputs. They must be committed before result inspection and cannot be expanded in response to outcomes.

## 7. Frozen counts

### Main matrix

- 50 pairs × 7 methods = 350 embeddings.
- 350 embeddings × 22 channels = 7,700 evaluations.

### Payload sweep

- methods: C0, C3_NP, C3;
- pairs: 10 preregistered sweep pairs;
- incremental payload levels: 25%, 50%, 75%;
- evaluation channels: Clean, JPEG Q=70, Gaussian variance=10, S&P density=0.03.

Counts:

- 10 × 3 × 3 = 90 embeddings;
- 90 × 4 = 360 evaluations.

The 100% payload operating point is reused analytically from the main matrix and is not recomputed as an incremental sweep embedding.

### PSNR sweep

- methods: C0, C3_NP, C3;
- pairs: the same 10 sweep pairs;
- incremental PSNR targets: 40.0, 42.5, 47.5 dB;
- evaluation channels: Clean, JPEG Q=70, Gaussian variance=10, S&P density=0.03.

Counts:

- 10 × 3 × 3 = 90 embeddings;
- 90 × 4 = 360 evaluations.

The 45.0 dB operating point is represented by the main matrix and is not recomputed as an incremental sweep embedding.

### Total

- embeddings: 350 + 90 + 90 = **530**;
- evaluations: 7,700 + 360 + 360 = **8,420**.

Any expansion requires a new protocol revision and run identity before outcomes are inspected.

## 8. Required measurements

Every evaluation must report, where applicable:

- complete and Base-only validity;
- header, Base, Detail, and complete integrity states;
- raw and protected recovery fractions;
- Base and Detail BER;
- unknown-bit fraction;
- codeword success, corrected-symbol count, correction radius, observed symbol errors, and overload;
- failure stage;
- reconstructed-secret PSNR, SSIM, MSE, and NCC;
- cover–stego quality;
- runtime, peak memory, worker allocation, cache status, and operational status.

Layer-specific values for baselines without Base/Detail semantics are `not_applicable`, never zero.

## 9. Execution order

1. validate protocol, manifests, schemas, baselines, and seeds;
2. pass unit, integration, transform, runtime-resume, and backup gates;
3. complete an engineering dry run on excluded inputs;
4. complete the locked five-pair operational pilot;
5. execute the 350 main embeddings;
6. execute 7,700 main evaluations;
7. execute payload sweep;
8. execute PSNR sweep;
9. verify completeness and remote backup;
10. run the preregistered analysis and manuscript generators.

No main scientific row may be scheduled before all pre-run gates pass.

## 10. Change control

After freeze, any change to methods, data, payload, transform, quality boundary, attack implementation, seeds, metrics, or analysis requires:

- a GitHub issue;
- a protocol revision;
- a new run ID;
- a comparability statement;
- preservation of all prior objects and failed attempts.

Selective rerunning, favorable-image selection, and outcome-driven matrix expansion are prohibited.
