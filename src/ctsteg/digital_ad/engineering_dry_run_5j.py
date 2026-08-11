"""Independent two-pair, seven-method engineering plan for FINAL-5J."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from ctsteg.provenance import sha256_file, sha256_json as provenance_sha256_json
from .engineering_worker_plan_5j import load_engineering_pairs, source_tree_fingerprint
from .runtime_5j import Runner5JError, sha256_json

PROTOCOL_ID = "FINAL-5J-v1"
PLAN_KIND = "seven_method_engineering_dry_run"
RUN_ID_PREFIX = "5j-eng"
METHODS = ("C0", "C1", "C2", "C3_NP", "C3", "B1", "B2")
EXPECTED_COUNTS = {
    "main_embeddings": 14,
    "main_evaluations": 308,
    "payload_sweep_embeddings": 0,
    "payload_sweep_evaluations": 0,
    "psnr_sweep_embeddings": 0,
    "psnr_sweep_evaluations": 0,
    "total_embeddings": 14,
    "total_evaluations": 308,
}


def _json(path: Path) -> dict[str, Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict):
        raise Runner5JError(f"JSON root must be an object: {path}")
    return value


def _baseline_fingerprints(root: Path) -> dict[str,str]:
    registry_path=root/"configs/5j/baseline_registry_v1.json"
    registry=_json(registry_path)
    if registry.get("status") != "frozen" or registry.get("main_run_authorized") is not True:
        raise Runner5JError("baseline registry is not frozen and authorized")
    output: dict[str,str]={}
    for method in ("B1","B2"):
        slots=[item for item in registry.get("slots",[]) if item.get("slot")==method]
        if len(slots)!=1 or slots[0].get("approved") is not True:
            raise Runner5JError(f"baseline {method} is not approved")
        contract=_json((root/str(slots[0]["contract_path"])).resolve())
        if contract.get("status") != "approved" or contract.get("license_review") != "compatible":
            raise Runner5JError(f"baseline {method} contract is not approved")
        output[method]=sha256_json(contract)
    return output


def _internal_fingerprint(method: str, source_fingerprint: str) -> str:
    return provenance_sha256_json({
        "protocol_id":PROTOCOL_ID,
        "payload_format_version":2,
        "method":method,
        "source_fingerprint":source_fingerprint,
    })


def _pair_seed(pair_id: str, channel: Mapping[str,Any]) -> int | None:
    if channel.get("stochastic") is False:
        return None
    base=channel.get("base_seed")
    if not isinstance(base,int):
        raise Runner5JError(f"channel {channel.get('id')} has invalid seed")
    material=f"{PROTOCOL_ID}:{pair_id}:{channel['id']}:{base}".encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8],"big") % (2**32)


def build_plan(
    pairs: Sequence[Mapping[str,str]],
    *,
    repository_root: str|Path,
    runtime_bindings_sha256: str,
) -> dict[str,Any]:
    root=Path(repository_root).resolve()
    if len(pairs)!=2:
        raise Runner5JError("seven-method engineering dry run requires exactly two pairs")
    source=source_tree_fingerprint(root/"src/ctsteg")
    config=root/"configs/5j/format_v2_layer_integrity.toml"
    seed_path=root/"configs/5j/seeds.lock.json"
    seed_lock=_json(seed_path)
    channels=seed_lock.get("channel_instances")
    if not isinstance(channels,list) or len(channels)!=22:
        raise Runner5JError("engineering dry run requires the frozen 22-channel seed lock")
    baseline=_baseline_fingerprints(root)
    method_fingerprints={m:(baseline[m] if m in baseline else _internal_fingerprint(m,source)) for m in METHODS}
    created_from={
        "study_plan_sha256":sha256_file(root/"configs/5j/study_plan_v1.json"),
        "seed_lock_sha256":sha256_file(seed_path),
        "main_manifest_sha256":sha256_file(root/"data-manifests/5j/main_50_pairs.csv"),
        "sweep_manifest_sha256":sha256_file(root/"data-manifests/5j/sweep_10_pairs.csv"),
        "baseline_registry_sha256":sha256_file(root/"configs/5j/baseline_registry_v1.json"),
        "config_sha256":sha256_file(config),
        "source_fingerprint":source,
        "engineering_manifest_sha256":sha256_file(root/"data-manifests/5j/dry_run.csv"),
        "runtime_bindings_sha256":runtime_bindings_sha256,
        "engineering_purpose_sha256":hashlib.sha256(PLAN_KIND.encode()).hexdigest(),
    }
    embeddings=[]; evaluations=[]
    for pair in pairs:
        for method in METHODS:
            material={
                "schema_version":1,"protocol_id":PROTOCOL_ID,"component":"main",
                "pair_id":pair["pair_id"],"cover_sha256":pair["cover_sha256"],
                "secret_sha256":pair["secret_sha256"],"method":method,
                "method_fingerprint":method_fingerprints[method],"payload_fraction":1.0,
                "target_psnr_db":45.0,"payload_format_version":2,**created_from,
            }
            embedding_id=sha256_json(material)
            embedding={k:material[k] for k in (
                "component","pair_id","cover_sha256","secret_sha256","method",
                "method_fingerprint","payload_fraction","target_psnr_db","payload_format_version"
            )}
            embedding["embedding_id"]=embedding_id
            embeddings.append(embedding)
            for channel in channels:
                seed=_pair_seed(str(pair["pair_id"]),channel)
                em={
                    "schema_version":1,"protocol_id":PROTOCOL_ID,"embedding_id":embedding_id,
                    "channel_instance_id":channel["id"],"family":channel["family"],
                    "severity":channel["severity"],"realization":channel["realization"],
                    "pair_seed":seed,**created_from,
                }
                evaluations.append({
                    "evaluation_id":sha256_json(em),"embedding_id":embedding_id,
                    "component":"main","pair_id":pair["pair_id"],"method":method,
                    "channel_instance_id":channel["id"],"family":channel["family"],
                    "severity":channel["severity"],"realization":channel["realization"],
                    "pair_seed":seed,
                })
    material={
        "schema_version":1,"protocol_id":PROTOCOL_ID,"created_from":created_from,
        "counts":dict(EXPECTED_COUNTS),"embeddings":embeddings,"evaluations":evaluations,
        "plan_kind":PLAN_KIND,
    }
    plan_id=sha256_json(material)
    return {**material,"plan_id":plan_id,"run_id":f"{RUN_ID_PREFIX}-{plan_id[:20]}"}
