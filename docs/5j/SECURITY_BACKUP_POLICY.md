# 5J Security and Backup Policy

Status: implementation baseline  
Protocol: `FINAL-5J-v1`

## 1. Non-negotiable rule

The research server is disposable compute. No code, configuration, input, result, cache object, checkpoint, log, manifest, evidence file, analysis output, or manuscript artifact may exist only on the server.

A completed object is not durable until its off-server copy has been uploaded and independently verified. The authoritative completion state is `committed_complete`, not merely `locally_complete`.

## 2. Secret boundary

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

A ciphertext and its decryption key must not be stored in the same GitHub account or repository. The file `/mnt/data/C8-privateKey.pem` is session input only and is explicitly prohibited from Git history and release assets.

## 3. Data classification

| Class | Examples | GitHub handling |
|---|---|---|
| Public | source code, protocol, schemas, public manifests, aggregate tables | normal version control |
| Restricted | licensed images, private capsule, raw evidence with redistribution limits | encrypted private artifact or approved private storage |
| Secret | keys, tokens, passwords, license credentials, recovery keys | GitHub secret store or separate custody; never Git objects |

## 4. Object lifecycle

Each scientific or operational object must pass these states:

1. `writing`
2. `locally_complete`
3. `locally_validated`
4. `hashed`
5. `uploaded`
6. `remote_verified`
7. `committed_complete`

The backup ledger records object ID, local path, SHA-256, byte size, encryption status, remote locator, upload time, verification time, and verification result.

A runner may reuse an object only when it is locally hash-valid. A server evacuation may remove an object only when the ledger records `remote_verified=true`.

## 5. Backup destinations

The implementation must support at least one GitHub-backed off-server destination and should support a second independent destination for restricted archives.

Acceptable GitHub-backed forms include:

- repository files for small public metadata;
- GitHub Releases for public immutable packages;
- workflow artifacts for temporary CI outputs, subject to retention limits;
- encrypted release assets or private-repository artifacts for restricted evidence.

GitHub workflow artifacts alone are not archival because retention may expire. Final evidence requires an immutable release/private archive plus a ledger entry.

## 6. Atomicity and failure handling

- Write files atomically through temporary paths and rename only after validation.
- Preserve failed attempts and operational logs.
- Never mark an upload complete before remote verification.
- A network failure must pause acknowledgement, not delete the local object.
- Checksum mismatch is fail-closed and requires a new upload identity.
- Scientific failures remain valid evidence; operational failures are classified separately.

## 7. Server evacuation gate

Before shutdown, reprovisioning, or deletion, the evacuation command must prove:

```text
complete_unbacked = 0
unuploaded_logs = 0
unuploaded_manifests = 0
remote_hash_mismatches = 0
unresolved_secret_files = 0
```

The evacuation report itself must be backed up and verified off-server.

## 8. Key rotation and incident response

If a secret is exposed or suspected to be exposed:

1. stop affected services;
2. revoke or rotate the credential immediately;
3. preserve audit logs without copying the secret value;
4. search repository history, releases, artifacts, logs, and issue text;
5. remove public exposure where possible, while assuming the old secret is compromised permanently;
6. document the incident, affected scope, rotation time, and replacement fingerprint;
7. rerun the security gate before research resumes.

Rewriting Git history is not a substitute for key rotation.

## 9. Acceptance gate

Phase 0 passes only when:

- plaintext-secret scanning is enabled;
- the backup-ledger schema exists;
- a synthetic object can be uploaded, restored, and hash-verified;
- evacuation rejects any unique server-only object;
- secret and recovery-key custody are documented outside the repository without revealing their values.
