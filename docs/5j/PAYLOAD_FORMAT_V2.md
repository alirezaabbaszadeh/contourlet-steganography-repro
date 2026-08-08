# FINAL-5J-v1 Payload Format v2: Layer Integrity

Status: **implementation specification**

## 1. Purpose

Format v1 validates only the complete `Base || Detail` payload. Consequently, a fully decoded and semantically useful Base layer cannot be declared valid when Detail fails. Format v2 adds independent Base and Detail integrity while retaining the same secret dimensions, Reed–Solomon profiles, encoded header size, total protected bit count, and cover–stego quality contract.

## 2. Compatibility boundary

- Format v1 remains readable and unchanged.
- Format v2 has a distinct `format_version=2` and configuration digest.
- v1 and v2 embeddings, cache objects, run IDs, and claims may not be mixed.
- The previous 88-evaluation archive remains immutable.
- The encoded header remains one RS(255,127) codeword: 255 bytes or 2,040 bits.
- The complete protected stream remains exactly 222,360 bits.

## 3. Header allocation

The raw header is still 127 bytes. The existing fixed prefix and final header CRC32 remain unchanged. Format v1 requires all 45 reserved bytes to be zero. Format v2 uses the first eight reserved bytes:

| Reserved offset | Size | Field |
|---:|---:|---|
| 0 | 4 bytes | Base raw-layer CRC32, big-endian |
| 4 | 4 bytes | Detail raw-layer CRC32, big-endian |
| 8–44 | 37 bytes | zero, reserved for future versions |

The existing `payload_crc32` continues to cover `Base raw bytes || Detail raw bytes`.

## 4. Flags

- bit 0: complete-payload CRC present;
- bit 1: independent Base/Detail CRC fields present.

Required values:

- format v1: `0b00000001`;
- format v2: `0b00000011`.

Unknown flag bits are rejected for these versions.

## 5. Encoding

For the exact 8,192-byte Base and 8,192-byte Detail raw layers:

```text
base_crc32    = CRC32(base_raw)
detail_crc32  = CRC32(detail_raw)
payload_crc32 = CRC32(base_raw || detail_raw)
```

CRC32 is an integrity/error-detection field, not a cryptographic authentication claim.

The Reed–Solomon profiles, scrambling, interleaving, body layout, and total bit allocation remain unchanged. C3_NP uses the C3 adaptive allocation and unequal profiles but the non-prioritized alternating layer transport layout.

## 6. Decoding states

The decoder reports exactly one primary validity state:

| State | Conditions |
|---|---|
| `complete_valid_recovery` | header valid, Base valid, Detail valid, complete CRC valid |
| `valid_base_only_recovery` | header valid, Base CRC valid, complete recovery invalid |
| `header_valid_no_valid_layer` | header valid, neither complete nor Base-only validity established |
| `header_failure` | header RS/CRC/config/method validation fails |
| `extraction_failure` | extraction/transform boundary fails before a valid stream is available |
| `operational_failure` | software, environment, resource, or infrastructure failure |

Detail-only validity is recorded diagnostically but does not produce a valid semantic output because Base contains the perceptually dominant high-order information.

## 7. Base-only reconstruction

A valid Base-only image is deterministic:

```text
reconstruction = (Base nibbles << 4) | 0
```

Equivalently, all Detail nibbles are zero. It may be emitted only when the complete Base raw layer is decoded and its format-v2 CRC32 matches. No ground-truth repair, nearest-neighbor bit replacement, or selective use of known secret bytes is permitted.

An image produced without valid Base integrity is `diagnostic_unverified` and cannot count toward Base-only Recovery Rate.

## 8. Required decode fields

- `format_version`;
- `validity_state`;
- `header_valid`;
- `payload_crc_valid`;
- `base_crc_valid` (`null` for v1);
- `detail_crc_valid` (`null` for v1);
- `base_bytes` and `detail_bytes` when RS decoding succeeds;
- complete recovered secret when complete validity holds;
- valid Base-only reconstruction when Base validity holds;
- explicit failures and codeword metadata.

## 9. False-validity tests

Implementation acceptance requires tests proving:

1. exact v1 clean decoding remains unchanged;
2. exact v2 clean decoding yields all three CRC decisions true;
3. corrupting Detail beyond ECC while leaving Base intact yields valid Base-only recovery and no complete recovery;
4. corrupting Base beyond ECC never yields valid Base-only recovery;
5. modifying a decoded Base byte without updating the header CRC cannot yield Base validity;
6. v1 streams never infer Base-only validity;
7. unknown versions, flags, and non-zero reserved bytes are rejected;
8. C3_NP and C3 differ only in the preregistered placement behavior.

## 10. Scientific interpretation

Format v2 does not guarantee robustness and must not convert an invalid stream into a success. It creates an auditable intermediate endpoint so methods that all fail complete recovery can still be compared by valid Base preservation, failure stage, layer BER, codeword survival, and ECC overload.