# Decision log

This is an append-only record of outcome-determining project decisions.
Clarifications may fix wording, but a changed decision receives a new ID and
supersedes the prior entry without deleting it.

## Summary

| ID | Date | Decision | Status |
|---|---|---|---|
| ADR-001 | 2026-07-27 | Freeze P0 numerical implementation | accepted |
| ADR-002 | 2026-07-27 | Separate digital A+D from P0 | accepted |
| ADR-003 | 2026-07-27 | Use a 128x128 Base/Detail secret contract | accepted |
| ADR-004 | 2026-07-27 | Evaluate A and D as a 2x2 factorial | accepted |
| ADR-005 | 2026-07-27 | Fix transport at 222,360 bits | accepted |
| ADR-006 | 2026-07-27 | Treat Haar as an engineering control only | accepted |
| ADR-007 | 2026-07-27 | Fail closed on transform capacity and writability | accepted |
| ADR-008 | 2026-07-27 | Separate digital attacks from P0 stress tests | accepted |
| ADR-009 | 2026-07-27 | Count unknown recovery as failure, not missing data | accepted |
| ADR-010 | 2026-07-28 | Audit one explicit MATLAB PDFB profile before adapter work | accepted |
| ADR-011 | 2026-07-28 | Use attack-averaged effective unrecovered-bit rate as the prospective primary endpoint | superseded by ADR-014 |
| ADR-012 | 2026-07-28 | Publish a result even if C3 is neutral or inferior | accepted |
| ADR-013 | 2026-07-28 | Protect the fixed header with RS(255,127) in format v1 | accepted; supersedes initial RS(255,223) suggestion |
| ADR-014 | 2026-07-28 | Replace the large final matrix with a lean 64/88-row case study | accepted; supersedes ADR-011 execution design |
| ADR-015 | 2026-07-28 | Require durable content-addressed execution and a real interruption gate | accepted |

## ADR-001 - Freeze P0 numerical implementation

**Context:** The source paper omits transform, datatype, and subband choices.
Changing the reconstruction while developing a new method would create a
moving baseline.

**Decision:** Protect the six numerical P0 files with SHA-256 hashes and CI.

**Consequence:** A correction that changes numerical P0 behavior requires a
new baseline version and cannot silently replace the frozen baseline.

## ADR-002 - Separate digital A+D from P0

**Context:** P0 carries a 512x512 analogue AP/GP/HP-transformed secret. The new
proposal is a bit-exact transport with error correction and different payload
semantics.

**Decision:** Place `DIGITAL_A_D` in an independent package, configuration,
CLI, benchmark, and analysis path. AP/GP/HP remains in P0.

**Consequence:** Digital results cannot be inserted into P0 tables as if the
protocols were identical.

## ADR-003 - Use a 128x128 Base/Detail secret contract

**Decision:** Convert the secret to 128x128 grayscale, split each pixel into
four MSBs (`Base`) and four LSBs (`Detail`), and preserve exact recombination.

**Rationale:** This creates two equally sized 65,536-bit semantic layers and a
net payload of 131,072 bits, or 0.5 bpp relative to a 512x512 cover.

## ADR-004 - Evaluate A and D as a 2x2 factorial

**Decision:** Use C0, C1, C2, and C3 so that adaptive allocation and unequal
protection have separate main effects and an explicit interaction.

**Consequence:** C3 versus C0 alone is not sufficient to attribute the source
of improvement.

## ADR-005 - Fix transport at 222,360 bits

**Decision:** Hold the complete protected payload constant across C0-C3.

**Consequence:** A transform with fewer than 222,360 eligible writable
coefficients fails the gate. Capacity is never reduced to rescue a profile.

## ADR-006 - Treat Haar as an engineering control only

**Decision:** Use four independent 256x256 orthonormal Haar subbands to verify
the full software path.

**Consequence:** Haar results support implementation claims but not contourlet
or article-superiority claims.

## ADR-007 - Fail closed on transform capacity and writability

**Decision:** Audit actual band structure, reconstruction, capacity, and
representative write/read behavior. Do not assume four 256x256 bands.

**Consequence:** A failed transform is negative evidence. No convenient proxy
is generated.

## ADR-008 - Separate digital attacks from P0 stress tests

**Decision:** The digital final suite contains JPEG, Gaussian, and
salt-and-pepper conditions. Rotation and crop remain P0 stress tests until a
registration/resynchronization mechanism is prospectively specified.

**Consequence:** The digital method cannot claim geometric robustness from P0
figures or from an unregistered stress test.

## ADR-009 - Count unknown recovery as failure

**Decision:** After RS or CRC failure, do not fabricate a recovered secret.
Use known-bit fraction, correct-recovered-bit fraction, and effective
unrecovered-bit rate.

**Consequence:** Complete failure receives no artificial recovery credit and
cannot disappear through survivor-only BER.

## ADR-010 - Audit an explicit MATLAB PDFB profile

**Decision:** Stage 0 locks `9-7`, `pkva`, `[2,2,2,2]`, and the fourth pyramid
level from coarse for one external Contourlet Toolbox interpretation.

**Consequence:** Even a runtime pass means only "eligible for human review."
It does not identify the authors' undisclosed settings.

## ADR-011 - Prospective primary endpoint

**Decision:** For each locked pair and method, average
`effective_unrecovered_bit_rate` over the nine digital final attacks after
averaging repeated seeds within attack. On the raw lower-is-better EUR scale,
orient C0 minus C3 so positive means lower unrecovered rate for C3.

**Minimum important difference:** 0.01 absolute, equivalent to one percentage
point of the 131,072 secret bits.

**Consequence:** The aggregate estimator must be implemented and tested before
the final data lock. Per-attack post hoc selection cannot replace it.

## ADR-012 - Publish neutral and negative outcomes

**Decision:** The manuscript and repository will retain and interpret a
neutral, mixed, or inferior C3 result.

**Consequence:** The project goal is a defensible comparison. A result that
does not support superiority changes the conclusion, not the data or
protocol.

## ADR-013 - Header protection in format v1

**Context:** The early design note suggested `RS(255,223)` for the header.
The implemented format defines a fixed 127-byte header containing the complete
config digest, payload metadata, payload CRC, reserved bytes, and header CRC.

**Decision:** Protect that complete header with one `RS(255,127)` codeword,
producing the fixed 2,040-bit header in format v1.

**Rationale:** This is stronger than the early 223-data-symbol suggestion,
fits the implemented fixed header exactly, and is constant across C0-C3.
Therefore it cannot create a D-factor advantage.

**Consequence:** `DIGITAL_AD_FORMAT_V1.md` and executable constants are
authoritative. Changing to `RS(255,223)` would require a new header map, format
version, payload accounting, tests, and prospective protocol version. It must
not be presented as a correction to existing v1 evidence.

## ADR-014 - Replace the large final matrix with a lean staged case study

**Context:** The earlier protocol required at least 50 pairs, five repeated
seeds, and nine attack severities, producing at least 10,000 result rows. That
scale was not used by the source article, exceeded the current case-study
claim, and added server cost without being necessary to identify A, D, or
their interaction.

**Decision:** Supersede ADR-011's nine-attack aggregate and repeated-seed plan
for the final DIGITAL_A_D study. Use four source-image traceability pairs,
C0-C3, and four mandatory channel conditions: Clean, JPEG 70, Gaussian
variance 10, and salt-and-pepper density 0.03.

The mandatory plan is 64 result rows from 16 saved embeddings. A predefined
hard check may add eight C0/C3 rows per triggered family at JPEG 50, Gaussian
variance 15, or salt-and-pepper density 0.05. The absolute cap is 88 rows.

There is one deterministic realization per pair and attack and no scientific
seed repetition. Population-level power analysis and inferential resampling
are outside this bounded case study.

**Consequence:** Results must be described only for the four named cases and
tested conditions. Neutral or negative core evidence ends the current study
unless a medium condition is objectively saturated. Exceeding 88 rows requires
a new decision and explicit budget approval before outcomes are viewed.

## ADR-015 - Require durable content-addressed execution

**Context:** A server interruption during the 64/88 run could otherwise lose
completed work, repeat costly embeddings, overwrite partial evidence, or leave
an ambiguous result set. Blindly increasing process count could also exhaust
RAM or create nested BLAS parallelism.

**Decision:** Execute the lean study through immutable content-addressed
embedding and channel-evaluation objects. Publish each object atomically only
after a deep SHA-256 inventory is complete. Treat the object store, not the
human-readable state file, as the resume authority. Preserve failed attempts,
stale locks, corrupt-object quarantine records, resource measurements, and
logs.

Use bounded process parallelism with automatic CPU/RAM limits and one
BLAS/OpenMP thread per worker. Require a fingerprint-bound gate that sends a
real `SIGKILL`, resumes the same task graph, proves cache reuse, and verifies a
self-contained checksum archive before `digital-research-run` may start.

**Consequence:** A completed numerical object is never repeated merely because
the coordinator, state file, documentation, or server restarted. A numerical
input or implementation change creates a new object address. An
orchestration-only fix does not invalidate valid numerical evidence. The
scientific matrix remains exactly 64 mandatory and at most 88 total rows; this
decision changes execution reliability, not experimental scope.
