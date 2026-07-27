# DIGITAL_A_D binary format version 1

This document locks the bit-exact transport used by `C0_FIXED`, `C1_A`,
`C2_D`, and `C3_A_D`. It is an engineering and research format. Its
scrambling and interleaving are deterministic randomization, not standard
cryptography.

## Image and bit order

- Cover: grayscale uint8, 512×512.
- Secret: grayscale uint8, 128×128.
- Pillow `L` grayscale conversion and bicubic resize.
- Post-inverse conversion: clip to `[0,255]`, then `floor(x+0.5)`, then uint8.
- Secret traversal: row-major.
- Base nibble: `(pixel >> 4) & 0x0F`.
- Detail nibble: `pixel & 0x0F`.
- Bits within every nibble and byte: MSB first.

Each layer contains 65,536 bits or 8,192 bytes. Recombination is
`(base << 4) | detail`.

## Reed--Solomon

Every codeword is a full systematic 255-byte word over GF(2^8):

- primitive polynomial `0x11D`;
- field generator `2`;
- first consecutive root `0`;
- zero padding at the end of a layer.

`RS(255,127)` corrects at most 64 erroneous byte symbols per codeword.
`RS(255,191)` corrects at most 32. A decoder rejection is recorded. A
miscorrection that happens to form a codeword is caught at payload level by
CRC32.

| Path | Base | Detail | Padding |
|---|---|---|---|
| C0/C1 | 32×RS(255,127), then 22×RS(255,191) | same | 74 bytes per layer |
| C2/C3 | 65×RS(255,127) | 43×RS(255,191) | 63 / 21 bytes |

C0/C1 use the same schedule for both layers; the first 32 input partitions are
the strong 127-byte partitions and the final 22 are the weak 191-byte
partitions.

## Header map

The raw header is exactly 127 bytes. It is protected by one RS(255,127)
codeword, producing 255 bytes or 2,040 embedded bits. Multi-byte integers are
big-endian.

| Offset | Bytes | Field |
|---:|---:|---|
| 0 | 4 | Magic `CTAD` |
| 4 | 1 | Format version |
| 5 | 1 | Method ID |
| 6 | 1 | Flags; bit 0 means semi-blind |
| 7 | 1 | ECC mode: 0 symmetric, 1 unequal |
| 8 | 2 | Secret width |
| 10 | 2 | Secret height |
| 12 | 1 | Base bit count |
| 13 | 1 | Detail bit count |
| 14 | 2 | Base codeword count |
| 16 | 2 | Detail codeword count |
| 18 | 2 | Base padding bytes |
| 20 | 2 | Detail padding bytes |
| 22 | 4 | Total embedded payload bits |
| 26 | 8 | Aggregate interleaver seed ID |
| 34 | 8 | Aggregate scrambler seed ID |
| 42 | 4 | Payload CRC32 |
| 46 | 32 | SHA-256 of the canonical digital config |
| 78 | 45 | Zero reserved bytes |
| 123 | 4 | Header CRC32 |

CRC is the IEEE/zlib CRC-32 variant. Header CRC covers bytes 0–122. Payload
CRC covers `base_raw || detail_raw` before padding and ECC.

The encoded header always occupies fixed, known coefficient slots. It is not
scrambled or interleaved, and its embedding weight is one.

## Seed serialization

The layer root is SHA-256 over:

```text
"ctsteg-digital-ad-v1\0"
master_seed as unsigned 128-bit big-endian
pair_id UTF-8 byte length as unsigned 16-bit big-endian
pair_id bytes
method_id as unsigned byte
layer_name ASCII byte length as unsigned byte
layer_name bytes
```

Separate substreams are `SHA256(layer_root || "\0" || purpose)` for purposes
`scramble` and `interleave`. The first 128 digest bits seed NumPy PCG64.
Artifacts store permutation SHA-256 values, NumPy/environment versions, and
aggregate 64-bit seed identifiers.

## Transport ordering

Encoding per layer is:

```text
RS → XOR scrambling → deterministic bit permutation
```

Decoding applies the exact inverse. C0, C1, and C2 alternate 2,040-bit
transport blocks from Base and Detail. C3 transports all Base blocks first and
then Detail so its high-score-first slot map can prioritize Base.

The final size for every method is:

- header: 2,040 bits;
- body: 220,320 bits;
- total: 222,360 bits;
- gross rate: 0.848236 bpp per 512×512 cover;
- net secret rate: 0.5 bpp.
