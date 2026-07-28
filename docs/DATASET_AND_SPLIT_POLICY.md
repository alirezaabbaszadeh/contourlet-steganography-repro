# Dataset and split policy

## Purpose

This policy prevents data leakage, input ambiguity, pair mismatch, and
post-result selection. It applies to all final `DIGITAL_A_D` experiments.
P0 traceability runs remain separate because they use a 512x512 analogue
secret contract.

## Data strata

### Paper-traceability stratum

Use the identifiable USC-SIPI covers named by the source article where
possible. This stratum checks traceability and supports descriptive comparison
with reported values.

It is not the primary generalization sample because:

- the article uses few covers;
- the exact cover-secret pairing is undisclosed;
- the label "Jet" is not a verified current catalogue identifier;
- the article's 512x512 secret differs from the digital 128x128 secret.

### Independent generalization stratum

Use a larger, independently sourced image collection whose license permits
research use and publication of identifiers or acquisition instructions. The
source, version, access date, license, and acquisition script must be frozen.

The final manuscript must distinguish results by stratum. The traceability
images may not be counted twice in the primary sample.

## Required splits

| Split prefix | Permitted use | Prohibited use |
|---|---|---|
| `calibration` | Estimate transform stability and fixed A features | Final effect estimation |
| `pilot` or `development` | Debug, dry-run, power variance, artifact checks | Final claims |
| `locked_test` | One final preregistered evaluation | Tuning or method selection |
| `traceability` | Descriptive P0/article comparison | Primary digital superiority |

No source image, derivative, near-duplicate, or content-equivalent image may
cross split boundaries.

## Sample-size rule

The locked digital sample contains:

```text
max(50, preregistered power-analysis requirement)
```

unique cover-secret pairs. The power calculation uses pilot variance, the
0.01 minimum important difference, at least 80% power, and the pair as the
unit. Its code and output are committed before locked outcomes are computed.

## Image identity

For every source image, record:

- stable source identifier;
- original filename and relative local path;
- source URL or acquisition command;
- license or terms reference;
- file SHA-256 before decoding;
- decoded-array SHA-256 after grayscale conversion and resize;
- width, height, mode, and decoder version;
- split and role (`cover` or `secret`).

The original image is never overwritten by preprocessing.

## Preprocessing

Version 1 fixes:

- cover output: 512x512;
- secret output: 128x128;
- grayscale: Pillow `L`;
- resize kernel: bicubic;
- uint8 range: 0 through 255;
- row order: top to bottom;
- column order: left to right.

Every method receives identical decoded arrays. Method code may not replace,
crop, denoise, normalize, or recolor metric references.

## Pair construction

Each locked pair must have:

- a filesystem-safe `pair_id`;
- one cover hash not used by another locked pair;
- one secret hash not used by another locked pair;
- a declared split;
- one row for each planned seed;
- deterministic notes identifying the pairing rule.

Pairing is generated once from sorted content hashes with a recorded seed.
Pairing may not be rearranged after method results are observed.

If unique secret images are unavailable, the primary study stops or adopts a
prospectively specified clustered analysis. It does not silently reuse secrets
while treating all pairs as independent.

## Seed schedule

The final seed set is:

```text
2026
2027
2028
2029
2030
```

Each `pair_id + seed` combination is a unique execution unit. The same seed is
used across C0-C3. Statistical inference averages repeated seeds within pair.

## Manifest schema

The executable CSV requires:

| Column | Rule |
|---|---|
| `pair_id` | Stable and filesystem-safe |
| `cover` | Path relative to the manifest or absolute |
| `secret` | Path relative to the manifest or absolute |
| `split` | One approved split label |
| `seed` | One of the locked final seeds |

Recommended provenance columns:

| Column | Meaning |
|---|---|
| `cover_source_id` | Dataset identifier |
| `secret_source_id` | Dataset identifier |
| `cover_license` | License reference |
| `secret_license` | License reference |
| `pairing_version` | Pair-generation rule version |
| `notes` | Non-outcome-based annotation |

Paths are operational metadata. File and decoded-array hashes establish
identity.

## Leakage and duplicate preflight

Before lock, a machine-readable preflight must verify:

1. every file exists and decodes;
2. every file SHA-256 matches the inventory;
3. no exact file or decoded-array hash crosses splits;
4. no perceptual near-duplicate crosses splits;
5. every locked pair has all five seeds;
6. no `pair_id + seed` is duplicated;
7. calibration and locked manifests have disjoint content;
8. all final paths resolve without manual editing;
9. each source has a recorded rights decision.

The preflight artifact and its implementation hash are part of the evidence
package.

## Freeze procedure

Before the final run:

1. write acquisition and preprocessing inventories;
2. generate the manifests;
3. run duplicate and leakage preflight;
4. compute manifest and inventory SHA-256 values;
5. record hashes in the protocol-lock artifact;
6. commit without result files;
7. tag or otherwise identify the immutable experiment commit;
8. execute only from a clean checkout of that state.

A changed byte, pairing, split, seed, or preprocessing dependency creates a
new experiment version.

## Data rights

Do not commit third-party images unless redistribution is explicitly allowed.
Prefer:

- acquisition scripts;
- stable identifiers;
- checksums;
- preprocessing instructions;
- small synthetic fixtures created by this project.

The source article and USC-SIPI assets retain their own terms. The repository's
MIT license applies only to repository-authored code and text.

## Missing or invalid inputs

An input that fails preflight is replaced only before lock using the documented
selection rule. After lock, it is recorded as an operational failure and any
replacement requires a new manifest version. Images are never removed because
they are difficult for C3.
