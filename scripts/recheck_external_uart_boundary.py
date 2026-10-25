"""Requalify boundary-only parser fix; recheck byte-identical fourth model source."""
from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
import shutil

from rtl_agent.common import ROOT, new_run_dir, sha256, write_json
from rtl_agent.uart_external.contract import DATA
from rtl_agent.uart_external.evaluator import evaluate, snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qualification", required=True)
    args = parser.parse_args()
    qualified = json.loads(Path(args.qualification).read_text())
    if not qualified["qualified"]:
        raise ValueError("Requalify original and maintainer control with corrected boundary before rechecking")
    prior = ROOT / "results/external_uart_compact_v1_20261023"
    previous = json.loads((prior / "summary.json").read_text())
    if previous["unique_paid_calls"] != 4:
        raise ValueError("Retain all four development requests")
    root = new_run_dir("external_uart_boundary_recheck", "results/external_uart_final_v1_20261023")
    for number in (1, 2, 3, 4):
        shutil.copytree(prior / f"attempt_{number}", root / f"attempt_{number}")
    for name in ("input.v", "protocol.json", "previous_protocol.json", "previous_initial_protocol.json", "previous_initial_two_request_summary.json"):
        (root / name).write_bytes((prior / name).read_bytes())
    (root / "initial_four_request_summary.json").write_bytes((prior / "summary.json").read_bytes())
    hashes = snapshot(root)
    for name, expected in qualified["checker_hashes"].items():
        if hashes[name] != expected:
            raise ValueError("Post-correction checker changed since control qualification")
    script = Path(__file__).resolve()
    (root / "checker_source" / script.name).write_bytes(script.read_bytes())
    old_protocol = json.loads((prior / "protocol.json").read_text())
    changes = {name: {"before": expected, "after": hashes.get(name)} for name, expected in old_protocol["checker_hashes"].items()
               if name != "scripts/run_external_uart_compact_context.py" and hashes.get(name) != expected}
    if set(changes) != {"rtl_agent/uart_external/contract.py"}:
        raise ValueError("Only the source-boundary policy may differ; simulation, formal properties, runner and agent must remain identical")
    old_contract = prior / "checker_source/rtl_agent__uart_external__contract.py"
    new_contract = ROOT / "rtl_agent/uart_external/contract.py"
    patch = "".join(difflib.unified_diff(old_contract.read_text().splitlines(True), new_contract.read_text().splitlines(True), fromfile="original_boundary_policy.py", tofile="corrected_boundary_policy.py"))
    (root / "boundary_policy_change.patch").write_text(patch)
    candidate_path = prior / "attempt_4/candidate.v"
    candidate = candidate_path.read_text()
    response = json.loads((prior / "attempt_4/response.json").read_text())
    raw = json.loads(response["choices"][0]["message"]["content"])
    if candidate != (DATA / "interface.vh").read_text() + raw["body"] + (DATA / "upstream_formal_suffix.vh").read_text():
        raise ValueError("Fourth candidate differs from the exact model body and unchanged pinned wrappers")
    record = {"posthoc_boundary_recheck": True, "previous_frozen_four_request_result": "POLICY_REJECTED",
              "reason": "Old boundary finder required a leading tab on the first production declaration. The raw model body omitted that indentation.",
              "candidate_unchanged_sha256": sha256(candidate.encode()), "model_body_exact_bytes_preserved": True,
              "checker_changes": changes, "semantic_simulation_and_formal_checkers_unchanged": True,
              "new_qualification": str(Path(args.qualification).resolve()), "new_api_calls": 0,
              "not_a_prospectively_frozen_four_call_success": True}
    write_json(root / "BOUNDARY_RECHECK.json", record)
    result = evaluate(candidate, root / "posthoc_boundary_recheck/evaluation")
    for name, expected in hashes.items():
        if sha256((ROOT / name).read_bytes()) != expected:
            raise ValueError("Checker changed during byte-identical recheck")
    report = {**previous, "accepted": result["accepted"], "accepted_source": "attempt_4/candidate.v" if result["accepted"] else None,
              "final_evaluation": result, "final_evaluation_location": "posthoc_boundary_recheck/evaluation",
              "posthoc_boundary_policy_fix": record, "qualification": args.qualification,
              "original_four_request_run_accepted": False, "new_api_calls_for_recheck": 0}
    write_json(root / "summary.json", report)
    print(json.dumps({"accepted": result["accepted"], "status": result["status"], "simulations": [s["passed"] for k in ("discovery_simulations", "audit_simulations") for s in result[k]],
                      "formal": [p["status"] for p in result["formal"]], "total_paid_calls": previous["unique_paid_calls"], "estimated_cost": previous["estimated_api_cost_usd"]}, indent=2))


if __name__ == "__main__":
    main()
