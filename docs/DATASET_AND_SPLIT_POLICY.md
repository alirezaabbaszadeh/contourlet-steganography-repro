# Lean dataset and pairing policy

## Purpose

This policy keeps the evidence set small, traceable, and aligned with the scale
of the source article. It replaces the earlier plan for a large independent
dataset, 50-or-more pairs, power analysis, and repeated seeds.

## Data strata

Only three bounded strata are allowed:

| Stratum | Maximum size | Use |
|---|---:|---|
| `pdfb_gate` | 1 canonical image | transform structure, reconstruction, capacity, and probe audit |
| `calibration` | 2 non-reporting pairs | create the fixed stability profile and catch implementation defects |
| `traceability_core` | 4 fixed pairs | all reported DIGITAL_A_D results |

Calibration rows are not counted as research outcomes. They must not be used to
choose a favorable attack, payload, PSNR, ECC layout, or method after comparing
C0-C3.

## Core covers

The four mandatory covers are the identifiable standard images discussed by
the source article:

1. Baboon;
2. Boat;
3. Peppers;
4. House.

For each file, record the stable source identifier, source URL or acquisition
command, license or terms reference, access date, original-file SHA-256, and
decoded-array SHA-256.

If an exact catalogue identity cannot be verified, mark that case unavailable
or explicitly qualified. Do not silently replace it and keep the original
label.

## Secret assignment

The source article's exact cover-secret pairing is undisclosed and its secret
size differs from the DIGITAL_A_D contract. Therefore:

- choose four fixed, licensed secret images before any result is viewed;
- preprocess each once to grayscale 128x128 uint8;
- bind one secret to each cover in the manifest;
- record the assignment rule and hashes;
- never rearrange pairs after outcomes exist.

This supports a controlled traceability case study, not author-equivalent
reproduction.

## Preprocessing

Version 2 retains:

- cover output: 512x512;
- secret output: 128x128;
- grayscale conversion: Pillow `L`;
- resize kernel: bicubic;
- uint8 range: 0 through 255;
- row order: top to bottom;
- column order: left to right;
- inverse-output clipping to `[0,255]`;
- half-up rounding before uint8 conversion.

All four methods receive identical decoded arrays and metric references.

## Manifest

The core manifest has exactly four rows, one per pair.

Required columns:

| Column | Rule |
|---|---|
| `pair_id` | stable and filesystem-safe |
| `cover` | resolvable source path |
| `secret` | resolvable source path |
| `split` | exactly `traceability_core` |
| `cover_source_id` | stable dataset identifier |
| `secret_source_id` | stable dataset identifier |
| `cover_sha256` | original file hash |
| `secret_sha256` | original file hash |
| `cover_array_sha256` | preprocessed array hash |
| `secret_array_sha256` | preprocessed array hash |

There is no experimental seed schedule and no repeated manifest row. If the
current CLI temporarily requires a legacy seed field, it carries one
deterministically derived implementation value only; validators must reject
duplicate `pair_id` rows.

## Deterministic channel realization

For stochastic channel implementations, derive one realization identifier from:

```text
SHA256(protocol_version || pair_id || attack_id)
```

Use the same realization for C0-C3. This controls pairing without creating an
experimental factor. The identifier cannot be changed after any outcome is
visible.

## Preflight

Before protocol lock, verify:

1. all eight source files exist and decode;
2. file and decoded-array hashes match the inventory;
3. dimensions, grayscale policy, and resize policy match the contract;
4. every cover and secret has a rights decision;
5. there are exactly four unique `pair_id` rows;
6. no pair is repeated for a second random realization;
7. calibration files do not overlap the four core pairs;
8. the run-budget calculator returns 64 mandatory rows and at most 88 total
   rows;
9. no result path exists before the locked run begins.

## Freeze procedure

Freeze these artifacts before generating core outcomes:

- acquisition instructions and source inventory;
- four-row core manifest;
- preprocessing version and decoder versions;
- secret assignments;
- PDFB transform fingerprint;
- core attack list;
- conditional triggers and hard attack list;
- code, configuration, and analysis hashes.

Changing a source byte, pair assignment, attack identity, transform, payload,
or PSNR target creates a new protocol version. It does not authorize additional
seeds or automatic dataset expansion.

## Claim boundary

The four cases support only statements explicitly bounded to those cases. They
do not support population-level confidence intervals or universal superiority.
A future generalization study must be proposed and budgeted separately after
the lean study is complete.

