"""Frozen two-call synthetic challenge; labels are joined only after all inference."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path

from rtl_agent.common import ROOT, new_run_dir, sha256, write_json
from rtl_agent.model_client import ModelError
from rtl_agent.mutations.agent import MAX_TOKENS, MODEL, SETTINGS, MutationClient, messages, parse_proposal
from rtl_agent.mutations.contract import DATA, AUDIT, DISCOVERY, FORMAL_PROFILES
from rtl_agent.mutations.evaluator import discovery_gate, evaluate, feedback, snapshot


def run_case(entry, root):
    case_id = entry["case_id"]
    directory = root / case_id
    directory.mkdir()
    source = (DATA / entry["source"]).read_text()
    if sha256(source.encode()) != entry["source_sha256"]:
        raise ValueError("Dataset source changed after sealing")
    (directory / "input.v").write_text(source)
    client = MutationClient()
    attempts, previous, observations = [], None, None
    record = {"case_id": case_id, "accepted": False, "accepted_source": None, "attempts": attempts}
    for number in (1, 2):
        folder = directory / f"attempt_{number}"
        folder.mkdir()
        prompt = messages(source, previous=previous, observations=observations)
        encoded = json.dumps(prompt)
        for hidden in ("mutation_map.json", "mutation_challenge_v1_author", "clean_control", "equivalent_control", "write_without_acceptance", "read_while_stalled", "reset_tail_retained", "over_accept_when_full", "sideband_swap"):
            if hidden in encoded:
                raise ValueError("Evaluation-only label entered the model context")
        write_json(folder / "messages.json", prompt)
        attempt = {"number": number, "status": "MODEL_RESPONSE_ERROR", "accepted": False}
        requests_before = client.inference_requests
        transport_error = False
        try:
            response = client.generate(prompt, max_tokens=MAX_TOKENS)
            write_json(folder / "response.json", response)
            proposal = parse_proposal(response, source)
            write_json(folder / "proposal.json", proposal)
            attempt["proposal"] = proposal
            result = evaluate(proposal["rtl"], folder / "evaluation")
            attempt.update({"status": result["status"], "accepted": result["accepted"], "evaluation": result,
                            "discovery_gate_passed": discovery_gate(result)})
        except ModelError as exc:
            attempt["error"], transport_error = client.redact(str(exc)), True
        except (ValueError, OSError, KeyError, IndexError, TypeError) as exc:
            attempt["error"] = client.redact(type(exc).__name__ + ": " + str(exc))
        attempt["cost"] = client.last_cost
        attempt["api_requests"] = client.inference_requests - requests_before
        write_json(folder / "attempt.json", attempt)
        attempts.append(attempt)
        if attempt["accepted"]:
            record.update({"accepted": True, "accepted_source": f"attempt_{number}/evaluation/candidate.v"})
        write_json(directory / "case.json", record)
        print({"case_id": case_id, "attempt": number, "status": attempt["status"], "decision": attempt.get("proposal", {}).get("decision"), "cost": attempt["cost"]}, flush=True)
        # The unexposed audit never determines a retry or enters feedback.
        if attempt.get("discovery_gate_passed") or transport_error:
            break
        previous = attempt.get("proposal") or {"response_unavailable": attempt.get("error", attempt["status"])}
        observations = feedback(attempt["evaluation"]) if "evaluation" in attempt else {"status": attempt["status"], "error": attempt.get("error")}
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--qualification", required=True)
    args = parser.parse_args()
    qualification = json.loads(Path(args.qualification).read_text())
    if not qualification.get("qualified"):
        raise ValueError("Qualify clean controls and all injected faults before model calls")
    directory = new_run_dir("mutation_repair_challenge", args.output)
    hashes = snapshot(directory)
    script = Path(__file__).resolve()
    hashes[str(script.relative_to(ROOT))] = sha256(script.read_bytes())
    (directory / "checker_source" / script.name).write_bytes(script.read_bytes())
    dataset = json.loads((DATA / "dataset.json").read_text())
    truth_path = ROOT / "research/mutation_challenge_v1_author/mutation_map.json"
    protocol = {"schema": 1, "synthetic_not_historical_defects": True, "max_requests_per_case": 2, "max_unique_requests": 16,
                "max_concurrent_cases": 2, "model": MODEL, "settings": SETTINGS.to_dict(), "max_output_tokens": MAX_TOKENS,
                "dataset_sha256": sha256((DATA / "dataset.json").read_bytes()), "truth_map_sha256": sha256(truth_path.read_bytes()),
                "checker_sha256": hashes, "discovery_profiles": DISCOVERY, "unexposed_audit_profiles": AUDIT,
                "formal_profiles": FORMAL_PROFILES, "pristine_rtl_used_for_scoring": False,
                "faulted_case_prompts_exclude_pristine_and_operator_map": True, "independent_context_per_case": True,
                "labels_joined_after_inference": True, "qualification": qualification,
                "audit_does_not_control_retries": True,
                "limits": "Eight constructed variants of one authored queue, including two controls. No real-world, external held-out, all-parameter or unbounded correctness claim; no general AI superiority claim."}
    write_json(directory / "protocol.json", protocol)
    sealed = {str(p.relative_to(ROOT)): sha256(p.read_bytes()) for p in
              [DATA / "dataset.json", DATA / "interface.vh", DATA / "contract.json", truth_path]
              + [DATA / entry["source"] for entry in dataset["cases"]]
              + [ROOT / name for name in ("rtl_agent/model_client.py", "rtl_agent/model_settings.py", "rtl_agent/budget.py", "configs/budget.json", "configs/pricing.json")]}
    write_json(directory / "sealed_inputs.json", sealed)
    client = MutationClient()
    client.verify_model()
    completed = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(run_case, entry, directory): entry["case_id"] for entry in dataset["cases"]}
        for future in as_completed(futures):
            completed.append(future.result())
            write_json(directory / "progress.json", {"completed": completed})
    for relative, expected in hashes.items():
        if sha256((ROOT / relative).read_bytes()) != expected:
            raise ValueError("Checker changed during model evaluation; do not report as a frozen run")
    for relative, expected in sealed.items():
        if sha256((ROOT / relative).read_bytes()) != expected:
            raise ValueError("Sealed input changed during model evaluation")
    # No worker receives this map. The join is for audit/reporting only.
    truth = {row["case_id"]: row for row in json.loads(truth_path.read_text())["cases"]}
    rows, costs = [], []
    for result in sorted(completed, key=lambda row: row["case_id"]):
        case_truth = truth[result["case_id"]]
        last = result["attempts"][-1]
        rows.append({"case_id": result["case_id"], "injected_fault": case_truth["injected_fault"], "operators": case_truth["operators"],
                     "kind": case_truth["kind"], "accepted": result["accepted"], "attempts": len(result["attempts"]),
                     "last_status": last["status"], "last_decision": last.get("proposal", {}).get("decision"),
                     "accepted_source": f"{result['case_id']}/{result['accepted_source']}" if result["accepted_source"] else None})
        costs += [attempt["cost"] for attempt in result["attempts"] if attempt["api_requests"]]
    failures = [row for row in rows if row["injected_fault"]]
    controls = [row for row in rows if not row["injected_fault"]]
    report = {"status": "COMPLETE", "cases": rows, "injected_cases": len(failures),
              "accepted_repairs": sum(row["accepted"] for row in failures), "normal_controls": len(controls),
              "controls_kept_unchanged": sum(row["accepted"] and row["last_decision"] == "keep" for row in controls),
              "unnecessary_control_repair_decisions": sum(row["last_decision"] == "repair" for row in controls),
              "unique_paid_calls": len(costs), "estimated_api_cost_usd": sum(cost.get("estimated_usd") or 0 for cost in costs if cost),
              "unsettled_requests": sum(not cost or cost.get("estimated_usd") is None for cost in costs),
              "fixed_reference_rtl_used_for_scoring": False, "scope": protocol["limits"]}
    write_json(directory / "summary.json", report)
    print(json.dumps({k: report[k] for k in ("status", "accepted_repairs", "injected_cases", "controls_kept_unchanged", "normal_controls", "unique_paid_calls", "estimated_api_cost_usd")}, indent=2))


if __name__ == "__main__":
    main()
