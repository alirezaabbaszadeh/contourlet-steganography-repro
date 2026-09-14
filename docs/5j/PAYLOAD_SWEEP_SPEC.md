# FINAL-5J-v1 Progressive Payload Sweep

Status: **implementation specification; frozen before scientific results**

## 1. Meaning of payload fraction

Payload fraction is the fraction of the 8 raw secret-image bits per pixel that is transmitted, always taking the most significant information first:

| Fraction | Transmitted bitplanes | Base bits/pixel | Detail bits/pixel | Raw bytes |
|---:|---|---:|---:|---:|
| 25% | bits 7–6 | 2 | 0 | 4,096 |
| 50% | bits 7–4 | 4 | 0 | 8,192 |
| 75% | bits 7–2 | 4 | 2 | 12,288 |
| 100% | bits 7–0 | 4 | 4 | 16,384 |

No spatial crop, pair-specific region selection, or outcome-driven bitplane selection is permitted.

## 2. Reconstruction

Omitted lower bitplanes are deterministically set to zero. Therefore a payload-valid reconstruction is:

- 25%: original secret masked with `0xC0`;
- 50%: original secret masked with `0xF0`;
- 75%: original secret masked with `0xFC`;
- 100%: exact original secret.

For fractions below 100%, `complete_valid_recovery` means complete validity of the **declared transmitted payload**, not bit-exact recovery of intentionally omitted bitplanes. The report must separately state declared-payload validity and full-secret reconstruction quality.

## 3. Reed–Solomon profiles

Profiles are deterministic and minimal for the declared layer bytes.

### Symmetric methods C0/C1

- 2-bit layer (4,096 bytes): 16 × RS(255,127) plus 11 × RS(255,191), 37 zero-padding bytes;
- 4-bit layer (8,192 bytes): the existing 32 strong plus 22 weak profile, 74 zero-padding bytes;
- absent layer: zero codewords and zero padding.

### Unequal methods C2/C3_NP/C3

Base:

- 2 bits: 33 × RS(255,127), 95 zero-padding bytes;
- 4 bits: 65 × RS(255,127), 63 zero-padding bytes.

Detail:

- 2 bits: 22 × RS(255,191), 106 zero-padding bytes;
- 4 bits: 43 × RS(255,191), 21 zero-padding bytes;
- absent Detail: zero codewords and zero padding.

## 4. Actual protected stream sizes

The encoded header remains 2,040 bits. Protected stream sizes differ by protection architecture at the lower raw payload levels:

| Raw fraction | C0/C1 protected bits | C2/C3_NP/C3 protected bits |
|---:|---:|---:|
| 25% | 57,120 | 69,360 |
| 50% | 112,200 | 134,640 |
| 75% | 167,280 | 179,520 |
| 100% | 222,360 | 222,360 |

This difference is not hidden or normalized away. It is the redundancy cost of unequal protection when only high-value information is present.

## 5. Analysis boundary

Primary payload-sweep interpretation is:

1. within-method recovery and reconstruction-quality curves across raw fractions;
2. recovery plotted against **actual protected bits**;
3. redundancy overhead plotted against raw information;
4. no direct superiority claim based only on the nominal 25/50/75% label when protected bits differ.

Cross-method comparisons at a sweep point must report both raw bytes and protected bits and discuss the unequal overhead.

## 6. Integrity behavior

- Base CRC covers the complete declared Base packed bytes;
- Detail CRC is `not_applicable` when Detail bits/pixel is zero;
- complete payload CRC covers `Base || Detail`, including an empty Detail;
- Base-only validity requires all declared Base bytes and the Base CRC;
- diagnostic reconstructions without valid Base integrity remain invalid.

## 7. Header and identity

The existing version-2 header fields `base_bits`, `detail_bits`, codeword counts, paddings, and `payload_bits` declare the operating point. Every object identity additionally includes raw payload fraction and actual protected bit count.

## 8. Acceptance tests

- exact pack/unpack for 2- and 4-bit layers;
- expected reconstructions for all four fractions;
- exact dynamic profile counts, paddings, and protected bits;
- clean declared-payload validity for C0, C3_NP, and C3 at every fraction;
- no Detail validity claim at 25% or 50%;
- format-v1 behavior remains fixed at 4+4 bits and 222,360 protected bits.