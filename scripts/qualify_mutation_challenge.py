"""Pre-model calibration: clean controls pass, all declared injected faults fail."""
import json

from rtl_agent.common import ROOT, new_run_dir, write_json
from rtl_agent.mutations.contract import DATA
from rtl_agent.mutations.evaluator import evaluate, snapshot


def main():
    out = new_run_dir("mutation_qualification")
    snapshot(out)
    dataset = json.loads((DATA / "dataset.json").read_text())
    truth = json.loads((ROOT / "research/mutation_challenge_v1_author/mutation_map.json").read_text())
    expected = {row["case_id"]: row for row in truth["cases"]}
    records = []
    for entry in dataset["cases"]:
        source = (DATA / entry["source"]).read_text()
        result = evaluate(source, out / entry["case_id"])
        row = {"case_id": entry["case_id"], "expected_injected_fault": expected[entry["case_id"]]["injected_fault"],
               "accepted": result["accepted"], "status": result["status"], "formal": [p["status"] for p in result["formal"]],
               "replays": [p.get("replay", {}).get("status") for p in result["formal"]],
               "discovery_pass": [s["passed"] for s in result["discovery_simulations"]], "audit_pass": [s["passed"] for s in result["audit_simulations"]]}
        records.append(row);write_json(out / "qualification.json", {"cases": records, "new_model_calls": 0})
        print(row, flush=True)
    qualified = all(row["accepted"] != row["expected_injected_fault"] for row in records)
    write_json(out / "qualification.json", {"cases": records, "new_model_calls": 0, "qualified": qualified,
               "fixed_reference_rtl_used_for_scoring": False, "synthetic_not_real_bug_discovery": True})
    print(out, flush=True)
    if not qualified:
        raise ValueError("Do not run repair inference before the independent checker qualifies")


if __name__ == "__main__":
    main()
