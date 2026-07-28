# Project charter

## Mission

Build a transparent research package that:

1. audits and independently reconstructs the 2026 Scientific Reports
   contourlet steganography article without claiming access to the authors'
   implementation;
2. evaluates a new digital Base/Detail method with adaptive allocation `A`
   and unequal protection `D`;
3. supports the strongest claim justified by frozen data and evidence, whether
   the result is positive, neutral, mixed, or negative.

The objective is credible evidence, not a predetermined superiority result.

## Core research question

At the same 512x512 cover size, 128x128 digital secret, protected payload,
preprocessing, PSNR constraint, transform interpretation, attack realization,
and evaluation code, do adaptive allocation and unequal error protection
improve secret recovery, separately or jointly?

The controlled study answers this question through the four methods:

| Method | Adaptive allocation and power `A` | Unequal protection `D` |
|---|---|---|
| `C0_FIXED` | off | off |
| `C1_A` | on | off |
| `C2_D` | off | on |
| `C3_A_D` | on | on |

## Architecture

### `P0_FROZEN`

P0 is the independent reconstruction of the source article. It contains the
AP/GP/HP interpretation, analogue secret-image embedding, the original
attack matrix, and reported-target audit. Its numerical files are protected by
[`p0_freeze_manifest.json`](p0_freeze_manifest.json).

P0 may receive documentation, test, packaging, or clearly separated adapter
work. Its frozen numerical implementation may not be changed to improve a
comparison.

### `DIGITAL_A_D`

The new method is a separate digital transport:

- grayscale cover: 512x512;
- grayscale secret: 128x128;
- four most-significant secret bits form `Base`;
- four least-significant secret bits form `Detail`;
- raw secret payload: 131,072 bits, or 0.5 bpp relative to the cover;
- protected transport: exactly 222,360 bits;
- deterministic scrambling and interleaving;
- sign embedding into an eligible coefficient pool;
- failure-aware decoding with no invented recovered secret.

AP/GP/HP does not enter this track.

### `TRANSFORM_PROFILES`

Transform identities are part of the claim:

| Profile | Role | Allowed interpretation |
|---|---|---|
| `proxy_directional_lp_v1` | Diagnose the existing Python directional proxy | Proxy only |
| `haar_orthogonal_control_v1` | Exercise the complete digital software path | Engineering control only |
| `matlab_pdfb_explicit_v1` | Audit one explicit external toolbox interpretation | Unverified interpretation until runtime review |

No unavailable PDFB structure may be replaced with a convenient proxy.

### `EVALUATION`

Shared evaluation owns:

- input manifests and hashes;
- deterministic preprocessing and attacks;
- protected metric references;
- raw long-form results;
- provenance and environment snapshots;
- pair-level inference and multiplicity correction;
- failure counts and negative results.

Method code cannot change evaluation references or attack realizations.

## Immutable version-1 decisions

| Item | Locked value or rule |
|---|---|
| P0 numerical source | Must match all six hashes in the P0 freeze manifest |
| Digital cover | 512x512, Pillow `L` grayscale |
| Digital secret | 128x128, Pillow `L` grayscale |
| Resize | Bicubic |
| Rounding | Half-up, followed by clipping to uint8 |
| Net payload | 131,072 bits |
| Protected payload | 222,360 bits |
| Header protection | One RS(255,127) codeword |
| Base protection with `D` | RS(255,127) |
| Detail protection with `D` | RS(255,191) |
| Target distortion | PSNR 45.0 dB with 0.1 dB tolerance |
| Adaptive power interval | 0.75 to 1.25 |
| Final digital attacks | JPEG 90/70/50, Gaussian variance 5/10/15, salt-and-pepper density 0.01/0.03/0.05 |
| P0-only stress tests | Rotation and crop |
| Primary failure-aware metric | `effective_unrecovered_bit_rate` |
| Seed aggregation | Average repeated seeds within image pair before inference |

The exact byte and codeword contract remains authoritative in
[`DIGITAL_AD_FORMAT_V1.md`](DIGITAL_AD_FORMAT_V1.md).

## Non-goals

This project does not:

- claim that the Python proxy is a Contourlet Toolbox reproduction;
- claim that the Haar control is a contourlet transform;
- call deterministic keyless AP/GP/HP a modern cryptographic primitive;
- retrofit C3 results into P0's 512x512 analogue-secret protocol;
- tune locked-test parameters after inspecting final outcomes;
- suppress algorithm failures or replace missing bits with guessed pixels;
- use higher PSNR, SSIM, histogram similarity, or visual inspection as proof
  of security;
- promise that C3 will outperform every baseline.

## Claim hierarchy

Claims must advance one level at a time:

1. **software validity** - deterministic contracts and tests pass;
2. **engineering-control validity** - C0-C3 execute under Haar without
   mislabelling the transform;
3. **explicit PDFB validity** - runtime Stage 0 passes and receives human
   review;
4. **mechanism evidence** - A, D, and A-by-D effects are estimated on a locked
   dataset;
5. **controlled empirical superiority** - the prospective success rule is met;
6. **direct article comparison** - payload, transform, data, attacks, and
   metrics are harmonized and the reconstruction claim is appropriately
   qualified;
7. **security claim** - requires a separate threat model and direct security
   evaluation, not the current image-quality evidence.

Skipping a level is prohibited. See
[`CLAIMS_AND_EVIDENCE.md`](CLAIMS_AND_EVIDENCE.md).

## Stage governance

Each stage has a fail-closed transition:

| Gate | Pass condition | Failure action |
|---|---|---|
| Transform structure | Capacity, reconstruction, identity, and writability pass | Preserve evidence; do not enable adapter |
| Clean C0 | All locked clean pairs decode at the PSNR constraint | Stop pilot and diagnose |
| Pilot | Artifact contract and all methods behave deterministically | Fix code using development data only |
| Calibration | Calibration-only manifest and transform fingerprint match | Reject stability artifact |
| Data lock | Rights, hashes, splits, pairs, seeds, and sample-size decision frozen | Do not run final benchmark |
| Final benchmark | All scheduled units accounted for, including failures | Preserve incomplete run and investigate operational errors |
| Statistics | Preregistered estimands generated from raw rows | Do not write superiority language |
| Manuscript | Claims map to archived artifacts and limitations | Do not submit |

## Definitions of done

### Software milestone

A software milestone is complete when:

- implementation and tests are committed;
- P0 freeze passes;
- documentation and decision log are updated;
- CI passes on the published commit;
- unsupported runtime results are not asserted.

### Experiment milestone

An experiment milestone is complete when:

- transform and clean gates pass;
- manifests and configurations are frozen before final execution;
- every expected unit has a status;
- raw results, failures, logs, hashes, and environment are retained;
- analysis is generated by committed code.

### Paper milestone

The paper package is complete when:

- the primary and secondary analyses are reproducible from raw results;
- every numerical table and figure is generated;
- the claim/evidence matrix is current;
- prior-art and threat-model sections support their own claims;
- positive, neutral, mixed, and negative findings are reported consistently;
- code, data acquisition instructions, manifests, and limitations are
  archived with persistent identifiers.

## Change control

An outcome-determining change after protocol lock requires:

1. a new entry in [`DECISION_LOG.md`](DECISION_LOG.md);
2. a version increment for the affected config, format, or protocol;
3. updated tests and documentation;
4. a new pilot;
5. a new locked experiment identifier.

Old evidence remains immutable and must not be overwritten.
