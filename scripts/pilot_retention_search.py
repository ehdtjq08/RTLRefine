"""Unpaid feasibility pilot; discovery alone selects, passive audit only scores."""
from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path

from rtl_agent.budget import BudgetLedger
from rtl_agent.common import ROOT, new_run_dir, sha256, write_json
from rtl_agent.known_bugs_v2.cases import DATA, load
from rtl_agent.known_bugs_v2.evaluator import evaluate
from rtl_agent.repair_search.retention import candidates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    case = load(args.case)
    source = (DATA / args.case / "input.v").read_text()
    options = candidates(source)
    if len(options) > 16:
        raise ValueError("Pilot cap is sixteen statically generated candidates")
    out = new_run_dir("retention_search_pilot", args.output)
    (out / "original.v").write_text(source)
    files = [Path(__file__).resolve(), ROOT / "rtl_agent/repair_search/retention.py"]
    sealed = {str(f.relative_to(ROOT)): sha256(f.read_bytes()) for f in files}
    dataset_seal = json.loads((DATA / "FROZEN.json").read_text())
    for name, expected in dataset_seal["checker_hashes"].items():
        if sha256((ROOT / name).read_bytes()) != expected:
            raise ValueError("Do not change the frozen V2 scorer for this pilot")
    protocol = {"case": args.case, "known_development_case": True, "neither_unseen_nor_paired_model_comparison": True,
                "generator": "Generic literal-default to existing-state replacement in the straight-line prefix of combinational blocks",
                "selection": "Source order; stop at first discovery pass even if passive audit fails", "candidate_cap": 16,
                "static_candidates": [{k:v for k,v in c.items() if k != "rtl"} for c in options],
                "generator_hashes": sealed, "source_sha256": sha256(source.encode()),
                "NVIDIA_calls": 0, "SMT_used": False, "corrected_RTL_used_to_generate_candidates": False,
                "scope": "One preselected known-case feasibility pilot, not a new algorithm, independent behavioral proof or improved benchmark score."}
    write_json(out / "protocol.json", protocol)
    before = BudgetLedger().summary()
    attempts, selected = [], None
    for option in options:
        folder = out / f"candidate_{option['index']:02d}"
        result = evaluate(args.case, option["rtl"], folder)
        row = {"candidate": {k:v for k,v in option.items() if k != "rtl"}, "evaluation": result}
        attempts.append(row)
        print({"candidate": option["index"], "state": option["state"], "status": result["status"]}, flush=True)
        if result["discovery_pass"]:
            selected = row
            break
    for name, expected in sealed.items():
        if sha256((ROOT / name).read_bytes()) != expected:
            raise ValueError("Generator changed during pilot")
    for name, expected in dataset_seal["files"].items():
        if sha256((DATA / name).read_bytes()) != expected:
            raise ValueError("Frozen V2 data changed during pilot")
    after = BudgetLedger().summary()
    assert before == after
    report = {"status": "COMPLETE", "static_candidate_count": len(options), "evaluated_candidates": len(attempts),
              "accepted": bool(selected and selected["evaluation"]["accepted"]), "selected": selected,
              "attempts": attempts, "paid_requests": 0, "budget_unchanged": True, "no_manual_functional_fix": True,
              "not_part_of_frozen_V2_results": True, "scope": protocol["scope"]}
    if selected:
        chosen = out / f"candidate_{selected['candidate']['index']:02d}" / "candidate.v"
        (out / "selected.patch").write_text("".join(difflib.unified_diff(source.splitlines(True), chosen.read_text().splitlines(True), fromfile="original.v", tofile="selected.v")))
    write_json(out / "summary.json", report)
    print(json.dumps({k:report[k] for k in ("accepted", "static_candidate_count", "evaluated_candidates", "paid_requests")}, indent=2))


if __name__ == "__main__":
    main()
