# Author Decision: Backup Only After Final Completion

Status: **authoritative author correction**  
Protocol: `FINAL-5J-v1`  
Decision date: 2026-08-06

This decision supersedes every earlier repository statement that requires remote backup, remote verification, or a backup-ledger acknowledgement during numerical execution.

## Correct requirement

Remote backup is performed **once, at the end of the project execution**, after all of the following are complete and locally validated:

1. all planned embeddings;
2. all planned evaluations;
3. payload and PSNR sweeps;
4. result aggregation and statistical analysis;
5. generated tables and figures;
6. manuscript and supplementary package;
7. final checksums and inventories.

During computation, progress is based on valid local cache/checkpoint objects. A task does not wait for upload or remote verification, and an evaluation does not wait for the embedding to be remotely backed up.

## Runtime rule

The operational sequence is:

```text
compute
→ atomic local checkpoint
→ local hash/schema validation
→ resume from local cache as needed
→ finish all computation and analysis
→ build one final archive/package
→ upload final backup
→ verify final backup
→ permit server deletion
```

The scheduler may use an embedding as soon as its local immutable object passes validation.

## Completion states

- `locally_complete`: a task has a valid local immutable object and counts toward execution progress.
- `run_complete_local`: all planned tasks and final analysis artifacts are locally complete.
- `final_backup_verified`: the final project archive has been uploaded and verified.
- `project_archived`: the backup ledger, checksums, and final package are complete and the server may be evacuated.

Per-object remote states such as `backup_pending` and `committed_complete` are not execution gates for FINAL-5J-v1.

## What remains unchanged

- atomic local writes and local SHA-256 validation;
- resumable content-addressed cache;
- preservation of operational failures and scientific failures;
- prohibition on committing plaintext keys, tokens, passwords, or license credentials;
- final remote backup verification before destroying or reprovisioning the server.

## Implementation priority after this correction

```text
select and implement B1/B2
→ freeze real input manifests and seeds
→ complete the simple local-cache runner
→ engineering dry run
→ main execution
→ analysis and manuscript
→ one final verified backup
```
