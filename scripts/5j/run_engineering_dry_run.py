#!/usr/bin/env python3
"""Run the two-pair, seven-method engineering dry run outside scientific results."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import sys

from ctsteg.digital_ad.engineering_dry_run_5j import (
    EXPECTED_COUNTS, METHODS, PLAN_KIND, RUN_ID_PREFIX, build_plan,
)
from ctsteg.digital_ad.engineering_worker_plan_5j import load_engineering_pairs
from ctsteg.digital_ad.runtime_5j import Runner5JError, validate_science_ready_report
from ctsteg.digital_ad.runtime_bindings_5j import validate_runtime_bindings
from ctsteg.digital_ad.runtime_dispatch_5j import Dispatch5JError, build_worker_context, run_local_study
from ctsteg.runtime import atomic_write_json


def parse_args() -> argparse.Namespace:
    root=Path(__file__).resolve().parents[2]
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path,default=root/"data-manifests/5j/dry_run.csv")
    p.add_argument("--runtime-bindings",type=Path,required=True)
    p.add_argument("--science-ready-report",type=Path,required=True)
    p.add_argument("--repository-root",type=Path,default=root)
    p.add_argument("--cache-dir",type=Path,required=True)
    p.add_argument("--run-dir",type=Path,required=True)
    p.add_argument("--workers",type=int,required=True)
    p.add_argument("--hard-cap",type=int,default=7)
    p.add_argument("--stop-after",choices=("embeddings",))
    p.add_argument("--json",action="store_true")
    return p.parse_args()


def main() -> int:
    args=parse_args()
    try:
        root=args.repository_root.resolve()
        readiness=validate_science_ready_report(args.science_ready_report)
        runtime=validate_runtime_bindings(args.runtime_bindings,check_files=True)
        pairs,pair_inputs=load_engineering_pairs(args.manifest,repository_root=root)
        plan=build_plan(pairs,repository_root=root,runtime_bindings_sha256=runtime["binding_sha256"])
        args.run_dir.mkdir(parents=True,exist_ok=True)
        plan_path=args.run_dir/"engineering_dry_run_plan.json"
        if plan_path.exists():
            existing=json.loads(plan_path.read_text(encoding="utf-8"))
            if existing!=plan:
                raise Runner5JError("engineering run directory contains a different plan")
        else:
            atomic_write_json(plan_path,plan)
        context=build_worker_context(
            plan,runtime_report=runtime,pair_inputs=pair_inputs,
            config_path=root/"configs/5j/format_v2_layer_integrity.toml",
            expected_counts=EXPECTED_COUNTS,run_id_prefix=RUN_ID_PREFIX,
            expected_plan_kind=PLAN_KIND,
        )
        summary=run_local_study(
            plan,context=context,cache_dir=args.cache_dir,run_dir=args.run_dir,
            workers=args.workers,hard_cap=args.hard_cap,stop_after=args.stop_after,
            expected_counts=EXPECTED_COUNTS,run_id_prefix=RUN_ID_PREFIX,
            expected_plan_kind=PLAN_KIND,
        )
        summary["scientific_evidence"]=False
        summary["engineering_pair_count"]=2
        summary["methods"]=list(METHODS)
        summary["science_ready_report_status"]=readiness.get("science_ready")
        atomic_write_json(args.run_dir/"engineering_dry_run_summary.json",summary)
    except (Runner5JError,Dispatch5JError,OSError,ValueError,RuntimeError,json.JSONDecodeError) as e:
        print(f"seven-method engineering dry run failed: {e}",file=sys.stderr); return 1
    print(json.dumps(summary,indent=2,sort_keys=True) if args.json else f"status={summary['status']} run_id={summary['run_id']} methods=7 scientific_evidence=false")
    return 0 if summary["status"] in {"embeddings_complete_local","run_complete_local"} else 2

if __name__=="__main__": raise SystemExit(main())
