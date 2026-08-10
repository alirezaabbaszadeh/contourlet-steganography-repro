# Ferdowsi Runner Operations

## Scope

This runbook covers the private repository-scoped GitHub Actions runner used to control the Ferdowsi research server. The public scientific repository must not own this runner and must not target it from public pull-request workflows.

## One-time runner registration

In the private control repository, open **Settings → Actions → Runners → New self-hosted runner**, select Linux and x64, and follow the GitHub-generated download, checksum, and configuration instructions on the server as the `ubuntu` user.

Use runner name `ferdowsi-48` and add label `ctsteg-ferdowsi-48`. The registration token is one-time bootstrap material: enter it only on the server and never paste it into chat, commit it, write it to a repository file, or preserve it in logs.

Install and start the configured runner as a service from its installation directory:

```bash
sudo ./svc.sh install ubuntu
sudo ./svc.sh start
sudo ./svc.sh status
```

The expected steady state is online/idle in the private repository and no self-hosted runner attached to the public scientific repository.

## Initial acceptance

Run the manual `Ferdowsi server health` workflow once. It must execute on labels `[self-hosted, linux, x64, ctsteg-ferdowsi-48]` and report only bounded host information. The expected target identity is hostname `48`, 48 logical CPUs, approximately 124 GiB visible memory, zero configured swap, Python 3.12, and Octave 8.4.

Routine chat-driven control does not use manual workflow dispatch. Adding exactly one JSON request under `requests/` triggers `Ferdowsi server control`, which validates the HEAD commit and request before execution.

## Nonsecret local control configuration

Copy `config/ctsteg-control.example.json` to `/etc/ctsteg-control.json` only after the referenced scientific paths have been finalized. The file contains paths only and must never contain passwords, SSH keys, GitHub tokens, MATLAB credentials, license material, or recovery keys.

Recommended ownership and mode:

```bash
sudo install -o root -g root -m 0644 config/ctsteg-control.example.json /etc/ctsteg-control.json
```

Edit path values locally if the finalized deployment uses different absolute paths, then run the health workflow and runtime checks again.

## Narrow final-run privilege boundary

`run_final_5j` must not receive general passwordless sudo. Install only the fixed helper and its exact sudoers rule:

```bash
sudo install -o root -g root -m 0755 server/ctsteg-control-final /usr/local/sbin/ctsteg-control-final
sudo install -o root -g root -m 0440 server/ctsteg-control-final.sudoers /etc/sudoers.d/ctsteg-control-final
sudo visudo -cf /etc/sudoers.d/ctsteg-control-final
```

The helper hardcodes `ctsteg-research@final.service` and accepts only `start` and `status`. Do not grant the runner account unrestricted `systemctl`, a root shell, or `NOPASSWD: ALL`.

## Allowed commands

The request validator accepts only:

- `health_check`
- `runtime_check`
- `bootstrap_check`
- `worker_benchmark`
- `research_status`
- `run_final_5j`

Every request identifies the scientific repository and an exact 40-character hexadecimal scientific commit SHA. `worker_benchmark` is capped at 44 workers for this host profile.

## Failure handling

A queued job while the runner is offline is not a scientific failure. Checkout/network failures, malformed requests, missing local control configuration, invalid paths, failed bootstrap/runtime gates, and missing exact commits fail without bypassing scientific readiness.

OOM, swap I/O, operational task failures, memory-floor breaches, and I/O-wait breaches make worker candidates unsafe according to the scientific worker policy. Scientific failures that the FINAL-5J protocol defines as valid evidence must remain scientific evidence rather than being converted into infrastructure retries.

## Firewall after acceptance

The temporary inbound SSH rule must not remain open to `0.0.0.0/0` after runner control is verified. Restrict TCP/22 to the trusted user public IP as `/32`, or disable external SSH when it is not required. Routine chat-to-server control uses the runner's outbound GitHub connection and does not require open inbound SSH.

## Service status and removal

From the runner installation directory:

```bash
sudo ./svc.sh status
sudo ./svc.sh stop
sudo ./svc.sh uninstall
```

Remove the runner from the private repository's Actions runner settings when decommissioning the server. Remove `/etc/sudoers.d/ctsteg-control-final` and `/usr/local/sbin/ctsteg-control-final` if the control plane is retired.

Before server shutdown after scientific completion, follow the scientific repository's archive, checksum, remote-backup, and `committed_complete` requirements; the runner is a control transport, not a replacement for scientific durability.
