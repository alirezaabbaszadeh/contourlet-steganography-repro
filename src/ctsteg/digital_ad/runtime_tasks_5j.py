"""Bind normalized plan tasks to deterministic executable worker payloads."""

from __future__ import annotations

from typing import Any, Mapping

from .runtime_5j import Runner5JError


_EMBEDDING_FIELDS = (
    "cover_sha256",
    "secret_sha256",
    "method_fingerprint",
    "payload_fraction",
    "target_psnr_db",
    "payload_format_version",
)


def embedding_index(plan: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    embeddings = plan.get("embeddings")
    if not isinstance(embeddings, list):
        raise Runner5JError("execution plan embeddings must be an array")
    output: dict[str, dict[str, Any]] = {}
    for raw in embeddings:
        if not isinstance(raw, Mapping):
            raise Runner5JError("execution plan contains an invalid embedding task")
        object_id = str(raw.get("embedding_id", ""))
        if not object_id or object_id in output:
            raise Runner5JError("embedding task ID is missing or duplicated")
        output[object_id] = dict(raw)
    return output


def bind_evaluation_task(
    evaluation: Mapping[str, Any],
    embedding: Mapping[str, Any],
) -> dict[str, Any]:
    """Add immutable embedding parameters needed by a standalone worker."""

    if evaluation.get("embedding_id") != embedding.get("embedding_id"):
        raise Runner5JError("evaluation/embedding object IDs do not match")
    for field in ("component", "pair_id", "method"):
        if evaluation.get(field) != embedding.get(field):
            raise Runner5JError(
                f"evaluation/embedding tasks disagree on {field}"
            )
    output = dict(evaluation)
    for field in _EMBEDDING_FIELDS:
        if field not in embedding:
            raise Runner5JError(f"embedding task is missing {field}")
        output[field] = embedding[field]
    return output


def bind_plan_evaluations(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    index = embedding_index(plan)
    evaluations = plan.get("evaluations")
    if not isinstance(evaluations, list):
        raise Runner5JError("execution plan evaluations must be an array")
    output: list[dict[str, Any]] = []
    for raw in evaluations:
        if not isinstance(raw, Mapping):
            raise Runner5JError("execution plan contains an invalid evaluation task")
        embedding_id = str(raw.get("embedding_id", ""))
        try:
            embedding = index[embedding_id]
        except KeyError as error:
            raise Runner5JError(
                f"evaluation references unknown embedding {embedding_id}"
            ) from error
        output.append(bind_evaluation_task(raw, embedding))
    return output
