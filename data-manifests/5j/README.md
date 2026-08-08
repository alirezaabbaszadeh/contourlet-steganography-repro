# 5J Data Manifests

The CSV files ending in `.template.csv` contain only the authoritative header. They are not experiment inputs and must never be passed to the scientific runner.

Final files to create during data freeze:

- `calibration.csv` — at least two engineering-only pairs;
- `dry_run.csv` — at least two infrastructure-test pairs;
- `main_50_pairs.csv` — exactly fifty preregistered scientific pairs;
- `sweep_10_pairs.csv` — exactly ten pairs selected deterministically from `main_50_pairs.csv`.

Run:

```bash
python scripts/5j/validate_inputs.py
python scripts/5j/validate_inputs.py --require-science-ready
```

The first command validates scaffolding and reports blockers. The second command must fail until all final manifests, rights, hashes, baseline approvals, and backup prerequisites are complete.

Do not commit private image bytes unless redistribution is explicitly permitted. For non-public inputs, commit metadata and SHA-256 values and reference a client-side encrypted private archive. Never store the archive decryption key in the same GitHub account.
