# Ferdowsi Server Control Plane Trigger Amendment

## Reason

The GitHub connector available to this chat can create and update repository files and inspect Actions runs and logs, but it does not expose a workflow-dispatch action. A control plane that depended only on manual `workflow_dispatch` would therefore still require the user to click GitHub for every operation.

## Revised trigger

The private control repository will run the server-control workflow on trusted pushes that add or modify files under `requests/*.json`.

Each control request is a newly created JSON file under `requests/`. The workflow checks out the private control repository and runs `python3 -m control.head_request`. That module inspects the exact Git `HEAD` commit using argv-based Git commands with `shell=False`, requires exactly one changed JSON request under `requests/`, resolves it through the existing traversal-safe request-path validator, and executes it through the existing allowlisted request runner.

The chat can therefore initiate work by committing one validated request file through the connected GitHub API. No GitHub Actions dispatch token, SSH connection, or arbitrary workflow input is required.

## Safety constraints

- The mechanism exists only in the private control repository.
- The self-hosted workflow has no `pull_request` trigger.
- A triggering commit must change exactly one `requests/*.json` file; zero or multiple request files fail closed.
- Request paths are NUL-delimited when read from Git to avoid whitespace parsing ambiguity.
- The request parser still accepts only the approved command allowlist and exact 40-character scientific SHA.
- Scientific worker count remains capped at 44.
- Scientific code is still fetched from the fixed public repository URL and detached at the exact requested SHA.
- No request can supply a shell command, repository URL, branch name, or arbitrary server path.
- GitHub-hosted CI remains separate from the self-hosted server workflow.

This amendment replaces only the routine trigger mechanism. A manual health workflow may still be kept as a human-operated diagnostic, but chat-driven control uses request-file commits.
