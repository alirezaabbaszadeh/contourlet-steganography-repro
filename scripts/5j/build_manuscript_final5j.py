#!/usr/bin/env python3
"""Generate manuscript-only TeX artifacts from the verified FINAL-5J snapshot."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import fmean

ROW_END = r"\\"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def finite(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        x = float(value)
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def fmt(x: float | None, digits: int = 4) -> str:
    return "N/A" if x is None else f"{x:.{digits}f}"


def tex_method(name: str) -> str:
    return name.replace("_", r"\_")


def write_main_table(method_rows: list[dict[str, str]], out: Path) -> None:
    order = ["C0", "C1", "C2", "C3_NP", "C3", "B1", "B2"]
    by_method = {r["Method"]: r for r in method_rows}
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\caption{Selected pair-level FINAL-5J method summaries generated from the frozen analysis artifact.}",
        r"\label{tab:5j-main-summary}",
        r"\begin{tabular}{lrrrrrr}",
        r"\toprule",
        "Method & Complete recovery & Payload correct & Raw BER & Cover PSNR (dB) & Runtime (s) & Operational failures " + ROW_END,
        r"\midrule",
    ]
    for m in order:
        r = by_method[m]
        lines.append(
            f"{tex_method(m)} & {r['Complete recovery mean']} & {r['Payload correct mean']} & "
            f"{r['Raw BER mean']} & {r['Cover PSNR mean']} & {r['Runtime mean (s)']} & "
            f"{r['Operational failures']} " + ROW_END
        )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def aggregate_sweep(raw_rows: list[dict[str, str]], emb: dict[str, dict], component: str, level_key: str):
    groups: dict[tuple[float, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in raw_rows:
        e = emb[row["embedding_id"]]
        if e["component"] != component:
            continue
        level = float(e[level_key])
        scope = "clean" if row["channel_family"] == "clean" else "attacked"
        groups[(level, row["method"], scope)].append(row)
    out = {}
    for key, rows in groups.items():
        complete = [finite(r["complete_recovery"]) for r in rows]
        payload = [finite(r["payload_correct_fraction"]) for r in rows]
        ber = [finite(r["raw_ber"]) for r in rows]
        psnr = [finite(r["cover_stego_psnr"]) for r in rows]
        out[key] = {
            "n": len(rows),
            "complete": fmean([x for x in complete if x is not None]),
            "payload": fmean([x for x in payload if x is not None]),
            "ber": fmean([x for x in ber if x is not None]),
            "cover_psnr": fmean([x for x in psnr if x is not None]),
        }
    return out


def clean_count(group: dict) -> str:
    return f"{round(group['complete'] * group['n'])}/{group['n']}"


def write_sweep_table(payload, psnr, out: Path) -> None:
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\caption{Descriptive FINAL-5J sweep results generated from raw evaluation rows joined to the frozen execution plan. BER values summarize the three attacked evaluation channels at each incremental operating point; attacked complete recovery was zero for all listed method--level cells.}",
        r"\label{tab:5j-sweeps}",
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        "Sweep & Operating point & C0 attacked BER & C3\\_NP attacked BER & C3 attacked BER & Clean complete (C0/C3\\_NP/C3) " + ROW_END,
        r"\midrule",
    ]
    for level in [0.25, 0.50, 0.75]:
        c0 = payload[(level, "C0", "attacked")]
        cnp = payload[(level, "C3_NP", "attacked")]
        c3 = payload[(level, "C3", "attacked")]
        clean = [payload[(level, m, "clean")] for m in ["C0", "C3_NP", "C3"]]
        cc = "; ".join(clean_count(x) for x in clean)
        lines.append(
            f"Payload & {int(level*100)}\\% & {fmt(c0['ber'])} & {fmt(cnp['ber'])} & {fmt(c3['ber'])} & {cc} " + ROW_END
        )
    lines.append(r"\midrule")
    for level in [40.0, 42.5, 47.5]:
        c0 = psnr[(level, "C0", "attacked")]
        cnp = psnr[(level, "C3_NP", "attacked")]
        c3 = psnr[(level, "C3", "attacked")]
        clean = [psnr[(level, m, "clean")] for m in ["C0", "C3_NP", "C3"]]
        cc = "; ".join(clean_count(x) for x in clean)
        lines.append(
            f"PSNR & {level:.1f} dB & {fmt(c0['ber'])} & {fmt(cnp['ber'])} & {fmt(c3['ber'])} & {cc} " + ROW_END
        )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, default=Path("docs/5j/final-run-20260812"))
    ap.add_argument("--output-dir", type=Path, default=Path("paper/generated"))
    args = ap.parse_args()
    snap, out = args.snapshot, args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    method_csv = snap / "tables/table_method_summary.csv"
    analysis_json = snap / "analysis/analysis.json"
    raw_csv = snap / "analysis/raw_evaluations.csv"
    plan_json = snap / "run/execution_plan.json"
    inventory = snap / "analysis/analysis_inventory.json"

    with method_csv.open(newline="", encoding="utf-8") as f:
        method_rows = list(csv.DictReader(f))
    analysis = json.loads(analysis_json.read_text(encoding="utf-8"))
    with raw_csv.open(newline="", encoding="utf-8") as f:
        raw_rows = list(csv.DictReader(f))
    plan = json.loads(plan_json.read_text(encoding="utf-8"))
    inv = json.loads(inventory.read_text(encoding="utf-8"))
    emb = {e["embedding_id"]: e for e in plan["embeddings"]}

    if len(raw_rows) != 8420 or inv["raw_row_count"] != 8420 or inv["missing_count"] != 0 or inv["invalid_count"] != 0 or inv["partial_analysis"]:
        raise SystemExit("verified FINAL-5J analysis completeness invariant failed")
    if plan["counts"]["total_embeddings"] != 530 or plan["counts"]["total_evaluations"] != 8420:
        raise SystemExit("frozen task-count invariant failed")

    def comparison(a: str, b: str, metric: str) -> dict:
        for r in analysis["primary_comparisons"]:
            if r["method_a"] == a and r["method_b"] == b and r["metric"] == metric:
                return r
        raise KeyError((a, b, metric))

    main_clean: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in raw_rows:
        e = emb[r["embedding_id"]]
        if e["component"] == "main" and r["channel_family"] == "clean":
            main_clean[r["method"]].append(r)

    c3c0comp = comparison("C3", "C0", "complete_recovery")
    c3c0ber = comparison("C3", "C0", "raw_ber")
    c3npcomp = comparison("C3", "C3_NP", "complete_recovery")
    c3npber = comparison("C3", "C3_NP", "raw_ber")
    c3b1comp = comparison("C3", "B1", "complete_recovery")
    c3b1payload = comparison("C3", "B1", "payload_correct_fraction")
    c3b1ber = comparison("C3", "B1", "raw_ber")
    c3b2comp = comparison("C3", "B2", "complete_recovery")
    c3b2payload = comparison("C3", "B2", "payload_correct_fraction")
    c3b2ber = comparison("C3", "B2", "raw_ber")
    by_method = {r["Method"]: r for r in method_rows}

    macros = {
        "FinalEmbeddings": "530",
        "FinalEvaluations": "8420",
        "FinalTasks": "8950",
        "FinalPairs": "50",
        "FinalWorkers": "20",
        "FinalBootstrap": "10000",
        "InternalCleanComplete": f"{sum(float(r['complete_recovery']) for r in main_clean['C3']):.0f}/50",
        "BOneCleanComplete": f"{sum(float(r['complete_recovery']) for r in main_clean['B1']):.0f}/50",
        "BTwoCleanComplete": f"{sum(float(r['complete_recovery']) for r in main_clean['B2']):.0f}/50",
        "CThreeCompleteMean": by_method["C3"]["Complete recovery mean"],
        "CThreePayloadMean": by_method["C3"]["Payload correct mean"],
        "CThreeBERMean": by_method["C3"]["Raw BER mean"],
        "BOneCompleteMean": by_method["B1"]["Complete recovery mean"],
        "BOnePayloadMean": by_method["B1"]["Payload correct mean"],
        "BOneBERMean": by_method["B1"]["Raw BER mean"],
        "BOneSecretPSNR": by_method["B1"]["Secret PSNR mean"],
        "BOneSecretSSIM": by_method["B1"]["Secret SSIM mean"],
        "BTwoCompleteMean": by_method["B2"]["Complete recovery mean"],
        "BTwoPayloadMean": by_method["B2"]["Payload correct mean"],
        "BTwoBERMean": by_method["B2"]["Raw BER mean"],
        "BTwoSecretPSNR": by_method["B2"]["Secret PSNR mean"],
        "BTwoSecretSSIM": by_method["B2"]["Secret SSIM mean"],
        "CThreeCZeroCompleteHolm": fmt(c3c0comp["holm_adjusted_p"], 6),
        "CThreeCZeroBERN": str(c3c0ber["paired_n"]),
        "CThreeCZeroBERDiff": fmt(c3c0ber["absolute_difference"]["mean"], 6),
        "CThreeCZeroBERCILow": fmt(c3c0ber["cluster_bootstrap"]["ci95_low"], 6),
        "CThreeCZeroBERCIHigh": fmt(c3c0ber["cluster_bootstrap"]["ci95_high"], 6),
        "CThreeCZeroBERHolm": f"{c3c0ber['holm_adjusted_p']:.3e}",
        "CThreeCNPCompleteHolm": fmt(c3npcomp["holm_adjusted_p"], 6),
        "CThreeCNPBERN": str(c3npber["paired_n"]),
        "CThreeCNPBERDiff": fmt(c3npber["absolute_difference"]["mean"], 6),
        "CThreeCNPHolm": fmt(c3npber["holm_adjusted_p"], 6),
        "CThreeBOnePayloadN": str(c3b1payload["paired_n"]),
        "CThreeBOnePayloadDiff": fmt(c3b1payload["absolute_difference"]["mean"], 4),
        "CThreeBOneBERDiff": fmt(c3b1ber["absolute_difference"]["mean"], 4),
        "CThreeBTwoCompleteDiff": fmt(c3b2comp["absolute_difference"]["mean"], 4),
        "CThreeBTwoCompleteHolm": fmt(c3b2comp["holm_adjusted_p"], 6),
        "CThreeBOneCompleteDiff": fmt(c3b1comp["absolute_difference"]["mean"], 4),
        "CThreeBOneCompleteHolm": fmt(c3b1comp["holm_adjusted_p"], 6),
        "CThreeBTwoPayloadN": str(c3b2payload["paired_n"]),
        "CThreeBTwoPayloadDiff": fmt(c3b2payload["absolute_difference"]["mean"], 4),
        "CThreeBTwoBERDiff": fmt(c3b2ber["absolute_difference"]["mean"], 4),
    }
    mlines = ["% Auto-generated by scripts/5j/build_manuscript_final5j.py; do not edit by hand."]
    mlines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in macros.items()]
    (out / "final5j_values.tex").write_text("\n".join(mlines) + "\n", encoding="utf-8")
    write_main_table(method_rows, out / "table_main_summary.tex")

    payload = aggregate_sweep(raw_rows, emb, "payload_sweep", "payload_fraction")
    psnr = aggregate_sweep(raw_rows, emb, "psnr_sweep", "target_psnr_db")
    write_sweep_table(payload, psnr, out / "table_sweep_summary.tex")

    inputs = [method_csv, analysis_json, raw_csv, plan_json, inventory]
    outputs = [out / "final5j_values.tex", out / "table_main_summary.tex", out / "table_sweep_summary.tex"]
    manifest = {
        "schema_version": 1,
        "protocol_id": plan["protocol_id"],
        "plan_id": plan["plan_id"],
        "run_id": plan["run_id"],
        "generator": "scripts/5j/build_manuscript_final5j.py",
        "inputs": [{"path": str(p), "sha256": sha256(p), "size": p.stat().st_size} for p in inputs],
        "outputs": [{"path": str(p), "sha256": sha256(p), "size": p.stat().st_size} for p in outputs],
    }
    (out / "final5j_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
