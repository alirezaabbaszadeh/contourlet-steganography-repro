# Ferdowsi Server Control Plane Design Amendment

This amendment refines the approved control-plane design after inspecting the exact CLI contracts in the scientific repository.

## Reason for amendment

The scientific entry points `scripts/5j/run_engineering_worker_trial.py`, `scripts/5j/research_status.py`, and `scripts/5j/run_research.py` require multiple mandatory paths such as manifests, runtime bindings, plans, cache directories, and science-readiness reports. Passing these paths through user-controlled workflow inputs would widen the control surface and make the original direct-dispatch sketch incomplete.

## Revised dispatch boundary

`control.dispatch.build_operation()` must never build a direct scientific command from request-supplied path strings. It returns an argv list that invokes the fixed module `control.operations` with:

- one allowlisted operation name;
- the already-verified detached scientific checkout path;
- the fixed server configuration path `/etc/ctsteg-control.json`;
- `--workers N` only for `worker_benchmark`, where `N <= 44` has already been validated.

`control.operations` loads `/etc/ctsteg-control.json`. That file contains only non-secret absolute paths to the frozen server resources required by the scientific scripts. It must not contain passwords, private keys, runner tokens, GitHub PATs, MATLAB credentials, or license material.

The operations layer validates configured paths and then invokes scientific scripts using `subprocess.run(argv, shell=False, ...)`. Missing or invalid configured resources fail closed before scientific execution.

## Security effect

This amendment narrows rather than expands the approved design:

- workflow requests still cannot provide arbitrary shell commands;
- workflow requests cannot provide arbitrary filesystem paths;
- scientific execution remains pinned to an exact 40-character commit SHA;
- worker count remains capped at 44;
- server-specific paths are local configuration, separate from repository requests;
- no secret is added to the control repository.

This amendment supersedes only the direct scientific argv examples in the implementation plan. All other approved design constraints remain unchanged.
