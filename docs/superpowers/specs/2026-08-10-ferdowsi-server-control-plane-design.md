# Ferdowsi Server Control Plane Design

## Goal

Create a secure control path that lets this project operate the Ferdowsi Cloud research server through GitHub Actions when direct inbound SSH from the ChatGPT runtime is unavailable.

## Context

The target server is reachable from the user's Windows host through Ferdowsi Cloud's external SSH endpoint, but direct TCP from the ChatGPT runtime is refused before SSH authentication. The scientific repository is public, so attaching an unrestricted self-hosted runner directly to it would unnecessarily expose the server to workflow execution risk from public-repository events.

## Chosen Architecture

Use a dedicated private control repository named `contourlet-steganography-control` and register one repository-scoped self-hosted GitHub Actions runner from the Ferdowsi server. The runner connects outbound to GitHub and is labeled `self-hosted`, `linux`, `x64`, and `ctsteg-ferdowsi-48`.

The public scientific repository remains the source of scientific code. Every control request that executes scientific code must identify an exact 40-character commit SHA. The control workflow checks out that SHA into a dedicated working directory and rejects floating branch names for scientific execution.

## Control Surface

The control plane intentionally does not accept arbitrary shell commands from workflow inputs. It accepts only an allowlist of operations:

- `health_check`: read-only host, CPU, memory, disk, swap, runtime and service inventory.
- `runtime_check`: verify Python, Octave, repository checkout and scientific runtime prerequisites.
- `bootstrap_check`: run the project's read-only bootstrap verification path.
- `worker_benchmark`: run the frozen worker-trial entry point using explicitly bounded worker counts.
- `research_status`: report current durable scientific progress without starting new work.
- `run_final_5j`: start or resume the final study only after all scientific readiness gates pass.

No workflow input is interpolated into an arbitrary shell command. Inputs are parsed and validated before dispatch.

## Repository Isolation

The control repository must be private. The self-hosted runner is registered at repository scope for that private repository only. Workflows in the public scientific repository continue using GitHub-hosted runners unless a later reviewed design explicitly changes that policy.

The control workflow must not run on `pull_request` from forks. Server execution is manual or request-file driven from trusted commits in the private control repository.

## Request Format

Control requests use a small JSON document committed under `requests/`. Required fields are:

```json
{
  "schema_version": 1,
  "command": "health_check",
  "scientific_repository": "alirezaabbaszadeh/contourlet-steganography-repro",
  "scientific_commit": "0123456789abcdef0123456789abcdef01234567"
}
```

Operation-specific fields are allowed only where defined. For `worker_benchmark`, the maximum accepted worker count is 44 for the current 48-vCPU host profile. Values above 44 are rejected unless a separately reviewed engineering-probe profile is introduced later.

## Server Identity and Worker Policy

The observed target host is Ubuntu 24.04.2 LTS with 48 online logical CPUs, approximately 124 GiB visible RAM, no configured swap, and an Intel Xeon E7-8890 v4 CPU model. The scientific worker policy reserves four logical CPUs for the operating system, monitoring, and I/O, so the current maximum worker count is 44. Internal numerical workers remain single-threaded.

The worker benchmark must preserve fail-closed gates for OOM, swap I/O, operational failures, memory floor, and I/O wait. Throughput winner selection is based on stable completed tasks per hour rather than maximum CPU utilization.

## Data and Secrets

No SSH private key, server password, GitHub registration token, GitHub PAT, MATLAB credential, license key, or recovery key may be committed to either repository or emitted in logs.

GitHub's self-hosted runner registration token is treated as one-time bootstrap material. It is entered or fetched directly on the server during initial registration and never sent through chat or stored in repository files.

Scientific datasets and large result objects remain on persistent server storage. GitHub receives only bounded logs, summaries, checksums, and explicitly uploaded small artifacts. Final scientific durability still follows the project's remote-backup and `committed_complete` rules.

## Runner Service

The runner executes as the non-root `ubuntu` account or a dedicated non-root account. System-level installation of the runner service may require one-time `sudo`, but workflow jobs themselves must not depend on unrestricted passwordless root access.

The runner is installed as a service so that it reconnects after reboot. The service must be independently identifiable and removable without affecting the scientific systemd services.

## Workflow Safety

The workflow must:

1. Reject unknown commands.
2. Reject malformed JSON and unknown fields.
3. Require an exact 40-character hexadecimal scientific commit SHA for operations that execute scientific code.
4. Reject `worker_benchmark` requests above 44 workers.
5. Record host identity, control request digest, scientific commit SHA, start/end timestamps, and exit status.
6. Preserve failed-attempt logs for audit.
7. Use timeouts for every operation.
8. Avoid destructive cleanup of scientific caches or result objects.
9. Never bypass existing runtime, input, backup, or science-readiness gates.

## Bootstrap Flow

Because direct SSH from the ChatGPT runtime is unavailable, only one bootstrap interaction is required from the already-working user SSH session:

1. Create or select the private control repository.
2. In GitHub repository settings, create a repository-scoped self-hosted Linux x64 runner and obtain the ephemeral registration command/token.
3. On the server, download the official GitHub Actions runner archive, verify the release checksum from GitHub's provided instructions, configure it against the private control repository with label `ctsteg-ferdowsi-48`, and install/start it as a service.
4. Verify in GitHub that the runner is online and idle.

After this point, normal health checks, runtime checks, worker benchmarking, status reads, and final execution control are initiated from the private control repository and inspected through GitHub Actions logs/artifacts from this chat.

## Error Handling

Failures are classified by boundary:

- Runner offline: control workflow remains queued; no scientific work starts.
- GitHub checkout/network failure: operation fails without mutating scientific state.
- Validation failure: exit before dispatch with configuration error.
- Bootstrap/runtime gate failure: stop and preserve evidence.
- Worker-trial operational failure/OOM/swap/I/O breach: mark candidate unsafe and do not promote it.
- Scientific task failure that is already defined as valid evidence by FINAL-5J: preserve according to the scientific protocol rather than treating it as an infrastructure retry.

No infinite retry loops are introduced. Existing project retry ceilings remain authoritative for bootstrap and research services.

## Testing

The control repository will contain unit tests for request validation and shell-free dispatch selection. CI for those tests runs on GitHub-hosted `ubuntu-latest`, not on the research server.

A dedicated manual `health-check` workflow targets only `[self-hosted, linux, x64, ctsteg-ferdowsi-48]`. Its first successful run is the acceptance test for the control plane. Scientific execution remains disabled until the existing project gates pass.

## Acceptance Criteria

The design is complete when:

- the private control repository exists;
- the repository-scoped runner appears online with the dedicated label;
- a manual health-check job runs on the Ferdowsi server and reports the expected host identity without secrets;
- arbitrary shell input is impossible through the supported workflow interface;
- scientific operations require an exact commit SHA;
- worker requests above 44 are rejected;
- the public scientific repository has no self-hosted runner attached to public PR workflows;
- the server remains scientifically fail-closed.
