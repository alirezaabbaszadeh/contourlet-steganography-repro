# 5J Security and Final Backup Policy

Status: **author-corrected implementation baseline**  
Protocol: `FINAL-5J-v1`

This policy implements the author decision in [`AUTHOR_DECISION_FINAL_BACKUP_ONLY.md`](AUTHOR_DECISION_FINAL_BACKUP_ONLY.md).

## 1. Backup timing

Remote backup is performed only after all planned computation, analysis, tables, figures, manuscript files, and final inventories are complete and locally validated.

Remote upload or verification must not:

- block embedding execution;
- block dependent evaluations;
- determine numerical progress;
- run between normal task batches;
- be required for local cache reuse or resume.

During execution, the persistent local server storage is the operational working store.

## 2. Local execution reliability

Every task must still use:

- atomic temporary-file writes followed by rename;
- immutable content-addressed object IDs;
- local SHA-256 and schema validation;
- resumable checkpoints;
- quarantine of incomplete or invalid attempts;
- separate records for scientific and operational failures.

A locally hash-valid object has state `locally_complete` and counts toward execution progress.

## 3. Final archive lifecycle

After the whole study is locally complete:

1. verify exact task counts and local object hashes;
2. generate final raw-data, analysis, table, figure, manuscript, log, and provenance inventories;
3. build the final public and restricted/encrypted packages;
4. upload the final packages to the approved remote destination;
5. download or independently verify the uploaded packages;
6. compare SHA-256 and byte sizes;
7. record remote identities and verification results in the final backup ledger;
8. mark the project `final_backup_verified`;
9. run the evacuation check before server deletion.

The backup tooling may retain per-file inventory entries, but per-object remote acknowledgement is not part of scheduling.

## 4. Secret boundary

Never commit or upload plaintext versions of:

- SSH private keys or PEM files;
- GitHub tokens;
- passwords;
- MATLAB credentials, license keys, or File Installation Keys;
- encryption or recovery keys;
- private dataset access credentials.

GitHub may contain only:

- public keys and fingerprints;
- secret names and rotation metadata;
- client-side encrypted ciphertext;
- checksums and recovery instructions that do not include the recovery key;
- GitHub Actions or Environment Secrets managed through GitHub's secret store.

A ciphertext and its decryption key must not be stored in the same GitHub account or repository. The file `/mnt/data/C8-privateKey.pem` is session input only and is prohibited from Git history and release assets.

## 5. Data classification

| Class | Examples | Final backup handling |
|---|---|---|
| Public | source, protocol, schemas, aggregate tables, redistributable outputs | repository or immutable release |
| Restricted | licensed images, private evidence, non-redistributable raw artifacts | client-side encrypted private archive |
| Secret | keys, tokens, passwords, credentials, recovery keys | never Git objects; separate secret custody |

## 6. Server evacuation gate

The server may continue computing with locally complete objects and no remote copy. It may not be destroyed, reprovisioned, or treated as safely disposable until the final archive has been verified.

Before deletion, the evacuation command must prove:

```text
planned_tasks_unaccounted = 0
invalid_local_objects = 0
missing_final_reports = 0
final_backup_verified = true
remote_hash_mismatches = 0
unresolved_secret_files = 0
```

## 7. Key rotation and incident response

If a secret is exposed or suspected to be exposed:

1. stop affected services;
2. revoke or rotate the credential immediately;
3. preserve audit logs without copying the secret value;
4. search repository history, releases, artifacts, logs, and issue text;
5. assume the old secret is permanently compromised;
6. document the incident and replacement fingerprint;
7. rerun the security gate before research resumes.

Rewriting Git history is not a substitute for key rotation.

## 8. Acceptance rule

The study execution is complete when all planned tasks and analysis artifacts are locally valid. The entire project is archived only after the single final remote backup is uploaded and verified.
