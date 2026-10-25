"""Frozen paired fork: same first proposal, then review versus checker feedback."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rtl_agent.common import ROOT, new_run_dir, sha256, write_json
from rtl_agent.model_client import ModelError
from rtl_agent.sequential.case_agent import CaseClient, MAX_TOKENS, MODEL, SCHEMA, SETTINGS, messages
from rtl_agent.sequential.case_review import CASES, evaluate, feedback, original_source


def request_candidate(client, case_id, baseline, directory, previous=None, observations=None):
    directory.mkdir()
    prompt = messages(case_id, baseline, previous=previous, observations=observations)
    write_json(directory / "messages.json", prompt)
    record = {"status": "RESPONSE_ERROR", "accepted": False, "proposal": None}
    try:
        response = client.generate(prompt, max_tokens=MAX_TOKENS)
        write_json(directory / "response.json", response)
        choice = response["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise ValueError("Completion did not finish")
        proposal = json.loads(choice["message"]["content"])
        if not isinstance(proposal, dict) or set(proposal) != {"rtl", "explanation"} or not isinstance(proposal["rtl"], str) or not isinstance(proposal["explanation"], str):
            raise ValueError("Unexpected proposal schema")
        write_json(directory / "proposal.json", proposal)
        record["proposal"] = proposal
        result = evaluate(case_id, proposal["rtl"], directory / "review", formal_on_failure=True)
        record.update({"status": result["status"], "accepted": result["accepted"], "review": result})
    except ModelError as exc:
        record.update({"error": client.redact(str(exc)), "transport_error": True})
    except (ValueError, OSError, KeyError, IndexError, TypeError) as exc:
        record["error"] = client.redact(type(exc).__name__ + ": " + str(exc))
    record["cost"] = client.last_cost
    write_json(directory / "attempt.json", record)
    print({"case": case_id, "request": str(directory.name), "status": record["status"], "cost": record["cost"]}, flush=True)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--trials", type=int, choices=(1, 2, 3), default=3)
    args = parser.parse_args()
    out = new_run_dir("sequential_paired_comparison", args.output)
    snapshot = out / "controller_source"
    snapshot.mkdir()
    hashes = {}
    files = sorted((ROOT / "rtl_agent/sequential").glob("*.py")) + [Path(__file__).resolve()]
    files += [ROOT / "rtl_agent" / name for name in ("model_client.py", "budget.py", "model_settings.py", "common.py", "tool_runner.py", "tool_paths.py")]
    for file in files:
        name = str(file.relative_to(ROOT)).replace("/", "__")
        content = file.read_bytes()
        (snapshot / name).write_bytes(content)
        hashes[str(file.relative_to(ROOT))] = sha256(content)
    protocol = {"design": "Paired fork with shared first proposal; second call self-review versus simulation and symbolic-counterexample feedback",
                "model": MODEL, "settings": SETTINGS.to_dict(), "max_output_tokens": MAX_TOKENS,
                "trials_per_case": args.trials, "cases": list(CASES), "per_arm_call_cap": 2,
                "max_unique_paid_calls": 3 * len(CASES) * args.trials,
                "same_initial_proposal_for_both_arms": True, "stop_both_arms_if_initial_accepted": True,
                "branch_order": "Alternate self-review first / checker-feedback first by case index plus trial index",
                "cost_accounting": "Unique paid calls counted once. Per-arm attributed cost includes the shared initial request and cannot be summed across arms.",
                "schema": SCHEMA, "controller_sha256": hashes, "reference_source_excluded_from_prompts": True,
                "not_a_blind_or_novel_bug_benchmark": True,
                "limitations": "Small development cohort of historical public bugs, potentially seen in model training. No held-out generalization, model superiority or unbounded proof implied. Symbolic input witnesses are not independently replayed."}
    write_json(out / "protocol.json", protocol)
    client = CaseClient()
    client.verify_model()
    pairs, paid = [], []
    stopped = False
    for case_index, case_id in enumerate(CASES):
        case_dir = out / case_id
        case_dir.mkdir()
        baseline = evaluate(case_id, original_source(case_id), case_dir / "baseline", formal_on_failure=True)
        if baseline["accepted"] or not baseline["simulations"] or all(s["passed"] for s in baseline["simulations"]):
            raise RuntimeError("Historical case did not independently reproduce")
        for trial in range(args.trials):
            trial_dir = case_dir / f"trial_{trial + 1}"
            trial_dir.mkdir()
            first = request_candidate(client, case_id, baseline, trial_dir / "shared_initial")
            paid.append({"path": str((trial_dir / "shared_initial").relative_to(out)), "cost": first["cost"]})
            pair = {"case": case_id, "trial": trial + 1, "shared_initial_status": first["status"], "arms": {}}
            branches = ["self_review", "checker_feedback"]
            if (case_index + trial) % 2:
                branches.reverse()
            for branch in branches:
                if first["accepted"] or first.get("transport_error"):
                    arm = {"accepted": first["accepted"], "calls": 1, "status": first["status"], "request_path": str((trial_dir / "shared_initial").relative_to(out)),
                           "attributed_cost_usd": first["cost"]["estimated_usd"] if first["cost"] else None}
                else:
                    if "review" in first:
                        observations = feedback(first["review"], trial_dir / "shared_initial/review")
                    else:
                        observations = {"status": first["status"], "error": first.get("error")}
                    previous = first["proposal"] or {"response_unavailable": first.get("error", first["status"])}
                    second = request_candidate(client, case_id, baseline, trial_dir / branch, previous,
                                               observations if branch == "checker_feedback" else None)
                    paid.append({"path": str((trial_dir / branch).relative_to(out)), "cost": second["cost"]})
                    costs = [r["cost"]["estimated_usd"] if r["cost"] else None for r in (first, second)]
                    arm = {"accepted": second["accepted"], "calls": 2, "status": second["status"], "request_path": str((trial_dir / branch).relative_to(out)),
                           "attributed_cost_usd": sum(costs) if all(c is not None for c in costs) else None}
                    if second.get("transport_error"):
                        stopped = True
                pair["arms"][branch] = arm
                if stopped:
                    break
            pairs.append(pair)
            write_json(out / "progress.json", {"pairs": pairs, "unique_paid_requests": paid})
            if first.get("transport_error") or stopped:
                stopped = True
                break
        if stopped:
            break
    for relative, expected in hashes.items():
        if sha256((ROOT / relative).read_bytes()) != expected:
            raise RuntimeError("Controller changed during comparison; do not report as a frozen run")
    complete = [p for p in pairs if set(p["arms"]) == {"self_review", "checker_feedback"}]
    totals = {branch: {"accepted": sum(p["arms"][branch]["accepted"] for p in complete), "pairs": len(complete),
                      "logical_calls": sum(p["arms"][branch]["calls"] for p in complete)} for branch in ("self_review", "checker_feedback")}
    costs = [p["cost"].get("estimated_usd") if p["cost"] else None for p in paid]
    summary = {"status": "STOPPED_ON_TRANSPORT_ERROR" if stopped else "COMPLETE", "pairs": pairs, "totals": totals,
               "unique_paid_requests": paid, "actual_unique_paid_calls": len(paid),
               "estimated_api_cost_usd": sum(c for c in costs if c is not None), "uncertain_cost_entries": sum(c is None for c in costs),
               "advantage_established": False, "scope": protocol["limitations"]}
    write_json(out / "summary.json", summary)
    print(json.dumps({key: summary[key] for key in ("status", "totals", "actual_unique_paid_calls", "estimated_api_cost_usd")}, indent=2))


if __name__ == "__main__":
    main()
