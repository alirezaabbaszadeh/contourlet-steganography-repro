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
| ADR-011 | 2026-07-28 | Use attack-averaged effective unrecovered-bit rate as the prospective primary endpoint | accepted pending analysis implementation |
| ADR-012 | 2026-07-28 | Publish a result even if C3 is neutral or inferior | accepted |
| ADR-013 | 2026-07-28 | Protect the fixed header with RS(255,127) in format v1 | accepted; supersedes initial RS(255,223) suggestion |

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
