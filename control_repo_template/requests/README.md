# Control requests

Each routine server action is triggered by committing exactly one new `*.json` file in this directory.

A request must use schema version 1, one allowlisted command, the fixed scientific repository name, and an exact 40-character scientific commit SHA. `worker_benchmark` additionally requires an integer `workers` value no greater than 44.

Never put passwords, keys, tokens, credentials, arbitrary shell commands, repository URLs, or server filesystem paths in a request.
