#!/usr/bin/env python3
"""Freeze a representative internal-task selection for worker benchmarking."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from ctsteg.digital_ad.runtime_5j import (
    Runner5JError,
    load_json_object,
    validate_execution_plan,
)
from ctsteg.digital_ad.worker_tuning_5j import canonical_sha256


INTERNAL_METHODS = ("C0", "C1", "C2", "C3_NP", "C3")
FAMILIES = ("clean", "jpeg", "gaussian", "salt_pepper")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--embedding-count", type=int, default=40)
    return parser.parse_args()


def _embedding_key(item: Mapping[str, Any]) -> tuple[Any, ...]:
    # Prefer payload diversity first, then distribute deterministically by method/pair.
    fraction = float(item.get("payload_fraction", 0.0))
    fraction_rank = {0.25: 0, 0.50: 1, 0.75: 2, 1.00: 3}.get(fraction, 9)
    return (
        fraction_rank,
        str(item.get("method", "")),
        str(item.get("pair_id", "")),
        float(item.get("target_psnr_db", 0.0)),
        str(item.get("embedding_id", "")),
    )


def _channel_rank(item: Mapping[str, Any]) -> tuple[Any, ...]:
    family = str(item.get("family", ""))
    severity = item.get("severity")
    preferred = {
        "clean": None,
        "jpeg": 70,
        "gaussian": 10,
        "salt_pepper": 0.03,
    }[family]
    exact = 0 if severity == preferred else 1
    realization = int(item.get("realization", 1))
    return (
        exact,
        abs(float(severity) - float(preferred)) if preferred is not None else 0.0,
        0 if realization == 1 else 1,
        realization,
        str(item.get("channel_instance_id", "")),
    )


def build_selection(plan: Mapping[str, Any], embedding_count: int) -> dict[str, Any]:
    if embedding_count < 32:
        raise Runner5JError("worker benchmark needs at least 32 embedding tasks")
    index = validate_execution_plan(plan)
    all_embeddings = [
        dict(item)
        for item in index["embedding_by_id"].values()
        if str(item.get("method")) in INTERNAL_METHODS
    ]
    if len(all_embeddings) < embedding_count:
        raise Runner5JError("finalized plan has too few internal embeddings")

    by_method: dict[str, list[dict[str, Any]]] = {
        method: [] for method in INTERNAL_METHODS
    }
    for item in sorted(all_embeddings, key=_embedding_key):
        by_method[str(item["method"])].append(item)
    if any(not values for values in by_method.values()):
        raise Runner5JError("worker benchmark cannot represent every internal method")

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    # First guarantee every method, then guarantee a second payload fraction.
    for method in INTERNAL_METHODS:
        item = by_method[method][0]
        selected.append(item)
        seen.add(str(item["embedding_id"]))
    present_fractions = {float(item["payload_fraction"]) for item in selected}
    if len(present_fractions) < 2:
        alternative = next(
            (
                item
                for item in sorted(all_embeddings, key=_embedding_key)
                if float(item["payload_fraction"]) not in present_fractions
            ),
            None,
        )
        if alternative is None:
            raise Runner5JError("worker benchmark requires two payload fractions")
        selected.append(alternative)
        seen.add(str(alternative["embedding_id"]))

    # Round-robin methods to avoid a prefix dominated by one method.
    cursors = {method: 0 for method in INTERNAL_METHODS}
    while len(selected) < embedding_count:
        progressed = False
        for method in INTERNAL_METHODS:
            values = by_method[method]
            while cursors[method] < len(values):
                item = values[cursors[method]]
                cursors[method] += 1
                object_id = str(item["embedding_id"])
                if object_id in seen:
                    continue
                selected.append(item)
                seen.add(object_id)
                progressed = True
                break
            if len(selected) >= embedding_count:
                break
        if not progressed:
            raise Runner5JError("unable to fill worker benchmark selection")

    evaluations_by_embedding: dict[str, list[dict[str, Any]]] = {}
    for item in index["evaluation_by_id"].values():
        evaluations_by_embedding.setdefault(str(item["embedding_id"]), []).append(
            dict(item)
        )

    evaluation_ids: list[str] = []
    for embedding in selected:
        object_id = str(embedding["embedding_id"])
        candidates = evaluations_by_embedding.get(object_id, [])
        for family in FAMILIES:
            matches = [
                item for item in candidates if str(item.get("family")) == family
            ]
            if not matches:
                raise Runner5JError(
                    f"embedding {object_id} has no {family} evaluation"
                )
            chosen = sorted(matches, key=_channel_rank)[0]
            evaluation_ids.append(str(chosen["evaluation_id"]))

    material = {
        "schema_version": 1,
        "protocol_id": "FINAL-5J-v1",
        "status": "frozen_before_trial",
        "plan_id": index["plan_id"],
        "run_id": index["run_id"],
        "selection_policy": "round_robin_internal_40_medium_channel_v1",
        "embedding_ids": [str(item["embedding_id"]) for item in selected],
        "evaluation_ids": evaluation_ids,
    }
    return {**material, "selection_sha256": canonical_sha256(material)}


def main() -> int:
    args = parse_args()
    try:
        plan = load_json_object(args.plan)
        selection = build_selection(plan, args.embedding_count)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(selection, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, Runner5JError) as error:
        print(f"worker trial selection failed: {error}", file=sys.stderr)
        return 1
    print(f"selection_sha256={selection['selection_sha256']}")
    print(f"embeddings={len(selection['embedding_ids'])}")
    print(f"evaluations={len(selection['evaluation_ids'])}")
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
