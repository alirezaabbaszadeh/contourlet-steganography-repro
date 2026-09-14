# FINAL-5J pre-production correction and comparability statement

Date: 2026-08-12
Authority: GitHub issue #9
Prior failed attempt: scientific SHA `f091d5a8fffeaa89bb9f00040420574674777ef6`, plan `e9d4bebdd15f6f99c8ba09aeec88c5073611466a340a91835dfaad2fe132a638`, run `5j-e9d4bebdd15f6f99c8ba`.

## Trigger

The first production dispatch was stopped fail-closed during the embedding stage. No planned evaluation was accepted as a final-study result. The preserved attempt exposed two distinct issues:

- main-plan internal method fingerprints used a different JSON canonicalization than the runtime worker;
- six preregistered B2 main covers had no clean-bit-exact embedding under the already frozen delta list and four-pass repair contract.

The six B2 pairs are:

- `coco-000000284725-000000389532`
- `coco-000000119445-000000358195`
- `coco-000000188465-000000167128`
- `coco-000000057725-000000406570`
- `coco-000000521259-000000506178`
- `coco-000000031735-000000273715`

A diagnostic on the last pair found nonzero clean BER for every frozen delta after all four allowed repair passes (minimum observed diagnostic bit-error count 94). Therefore no delta expansion, repair-pass expansion, favorable-cover substitution, or selective rerun is authorized.

## Corrections

1. Internal method fingerprints in the main plan use the worker's provenance canonicalization. Plan/task ID canonicalization is not changed.
2. Exact clean-candidate exhaustion is materialized as scientific prerequisite infeasibility. The embedding becomes an immutable `scientific_failure`; every dependent planned evaluation becomes an immutable `scientific_failure` with typed `not_evaluated` reason and S5/extraction-failure classification. Other exceptions remain operational failures.
3. The B2 numerical/algorithmic contract is unchanged: same capacity, same payload, same target PSNR selection, same frozen delta candidates, same maximum four repair passes.

## Comparability

The corrected run retains exactly the same preregistered pair/method/attack matrix and 530/8,420 planned counts. Results from the failed f091/e9d4 attempt are not mixed into the corrected run. The corrected run receives a new baseline freeze, scientific SHA, plan ID, run ID, cache namespace, and output namespace.

The 32c64g worker selection remains 20 because the correction does not change the five-internal-method engineering workload used for worker autotuning. A fresh seven-method dry run at 20 workers is nevertheless required before the corrected production run.
