# Server reprovisioning and continuation runbook

> **Historical scope notice.** This runbook documents the pre-FINAL-5J CPU8 traceability run (the 16-embedding / up-to-88-row execution) and is retained for operational history. It is **not** the authoritative runbook or evidence contract for the current FINAL-5J article. For the current frozen study, use `docs/ARTICLE_FREEZE.md` and `docs/5j/final-run-20260812/README.md`.

This document records the operational knowledge from the completed CPU8 run so a future server can be rebuilt without repeating the same trial-and-error. It is an operational guide, not a claim that the source article has been exactly reproduced.

## 1. What must be restored

Restore the exact research commit and the private reproduction capsule before starting a new experiment. The capsule contains the input manifests and image-derived inputs, the complete Contourlet tree, environment inventories, evidence logs, the offline Git bundle, restore instructions and the validated 88-object result archive.

Recorded identifiers:

- Repository: `alirezaabbaszadeh/contourlet-steganography-repro`
- Branch used for the final run: `agent/runtime-resume-gate`
- Numerical execution commit: `7ff0c5abf4511c803a935645dcc2c3ed012f05e9`
- Final reporting commit: `c564d209844a9dfdb74bf9031fa1ddf3af72cad4`
- Final manuscript/archive package commit: `a51b51e` (later archive publication: `f1ab561`)
- Final run ID: `f7acf6d9d31dd66cddf1`
- Runtime gate: `20260730T134046Z-98265862`

The private capsule hash is `d88a022b2cfca54ab2c9572bd6d0a442a61f169d97c4e27ffe59ef0adccd431d`. The final result archive hash is `5a367ddb07c3df88c2a3ea7ec38187d1ea195e898a61baaa8e733d6dd347b663`.

## 2. Provisioning order

1. Create a clean Ubuntu server with enough RAM for the locked worker policy; do not choose worker count by CPU count alone.
2. Install the pinned system packages and record `dpkg-query` before installing project packages.
3. Install the repository in an isolated Python environment and record `pip freeze`.
4. Restore the exact Contourlet toolbox tree and verify its 72-file SHA-256 inventory.
5. Restore the 27 input files and verify their SHA-256 inventory.
6. Checkout the recorded numerical commit before any code modification.
7. Run the full deterministic test suite before starting the research runner.
8. Run the PDFB Stage-0/transform gates and archive their reports.
9. Run the runtime gate, including the real `SIGKILL` recovery check, before scheduling scientific rows.
10. Start the bounded runner through the systemd template only after the gate passes.

Never start a new scientific run from an unverified `main` checkout, an unverified toolbox copy, or a partially restored input directory.

## 3. Failures encountered and the successful fixes

### Parquet export failure

The first service attempt failed during report export because mixed-type metric fields were serialized directly into Parquet. This was an export/schema failure, not a scientific failure. The successful fix was to project metric fields into a typed, stable schema before writing Parquet. The corrected reporting commit was `c564d209844a9dfdb74bf9031fa1ddf3af72cad4`.

Do not “fix” this by deleting the failed service output or rerunning all numerical work. Preserve the failed log, apply the typed projection, resume from immutable cache objects, and verify that no embedding or channel object is recomputed.

### Resume after interruption

The durable runner was designed to resume from content-addressed objects and atomic checkpoints. The successful final run reused 16 embeddings, 48 core channels and 24 hard checks. A resume must report cache hits and must preserve the original object hashes.

### Transform interpretation boundary

The missing author filter names, directional schedule, subband indices, boundary rules and datatype choices cannot be repaired by guessing. The accepted operational solution was to use an explicit, independently named `9-7`, `pkva`, `[2,2,2,2]` PDFB interpretation and keep it separate from any author-equivalent claim. Do not relabel the proxy or silently substitute a different MATLAB configuration.

## 4. Locked execution contract

The final protocol has 16 embeddings, 64 mandatory rows and at most 24 conditional hard-check rows, for a maximum of 88 rows. Core channels are Clean, JPEG quality 70, Gaussian variance 10 and salt-and-pepper density 0.03. Triggered hard families in the completed run were Gaussian, JPEG and salt-and-pepper.

The contract is fixed at 222,360 protected bits and a target PSNR of `45.0 +/- 0.1 dB`. The C0--C3 method definitions, Base/Detail protection, CRC header, scrambling, interleaving, clipping, rounding and semi-blind extraction must remain identical across methods.

## 5. Acceptance checklist before spending compute

- `git status` is clean and the checkout matches the recorded commit.
- Input and toolbox inventories have zero SHA-256 mismatches.
- Python and system package inventories are archived.
- The transform fingerprint matches the configuration.
- All deterministic tests pass.
- The runtime gate passes, including real `SIGKILL` recovery.
- The worker count and memory reserve are recorded.
- The planned row count is exactly 64 core plus triggered checks, never above 88.
- The service writes logs and checkpoints to persistent disk.
- Failed attempts remain available for audit.
- The report exporter uses the typed Parquet projection.

If any item fails, stop before launching the scientific runner. A server being reachable is not evidence that it is scientifically ready.

## 6. After the run

Validate `run_summary.json`, all raw CSV/JSON/JSONL/Parquet rows, the archive checksum and the runtime-gate report. Copy the final archive and the complete capsule off the server before shutdown. Record the run ID, commit IDs, hashes, trigger decisions and any operational failure in the repository. Only then is the server disposable.

## 7. Reproducibility principle

The next run must be additive. It may use a new registered configuration or a new transform interpretation, but it must not overwrite the locked result objects or expand the attack matrix merely because the first result was negative. The archive and this runbook are the memory of the server; the machine itself is not.
