"""Presealed known historical bugs: shared first call, equal-cap paired fork."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import threading

from rtl_agent.budget import BudgetLedger
from rtl_agent.common import ROOT, new_run_dir, sha256, write_json
from rtl_agent.model_client import ModelError
from rtl_agent.known_bugs_v2.agent import KnownBugClient, MODEL, MAX_TOKENS, SETTINGS, SCHEMA, messages, parse_proposal
from rtl_agent.known_bugs_v2.cases import DATA, load, canonical
from rtl_agent.known_bugs_v2.evaluator import evaluate, feedback, snapshot

RUN_CAP_USD = 5.0


def request_candidate(client, case, original, dependencies, directory, *, previous=None, observations=None):
    directory.mkdir()
    prompt = messages(case, original, dependencies, previous=previous, observations=observations)
    encoded = json.dumps(prompt)
    if any(token in encoded for token in ("control_sources", "maintainer_fixed", "trace_1/", "trace_2/", "unexposed_payload_transform_")):
        raise ValueError("Evaluation-only context leak")
    write_json(directory / "messages.json", prompt)
    record = {"status": "RESPONSE_ERROR", "accepted": False, "discovery_pass": False, "audit_pass": False, "proposal": None}
    before = client.inference_requests
    try:
        response = client.generate(prompt, max_tokens=MAX_TOKENS)
        write_json(directory / "response.json", response)
        proposal, source = parse_proposal(response, original)
        record["proposal"] = proposal
        write_json(directory / "proposal.json", proposal)
        (directory / "candidate.v").write_text(source)
        result = evaluate(case["id"], source, directory / "evaluation")
        record.update({"status": result["status"], "accepted": result["accepted"], "discovery_pass": result["discovery_pass"],
                       "audit_pass": result["audit_pass"], "evaluation": result,
                       "functional_source_changed": canonical(source) != canonical(original)})
    except ModelError as exc:
        record.update({"error": client.redact(str(exc)), "transport_error": True})
    except (ValueError, RuntimeError, OSError, KeyError, IndexError, TypeError) as exc:
        record["error"] = client.redact(type(exc).__name__ + ": " + str(exc))
    record.update({"cost": client.last_cost, "api_requests": client.inference_requests - before})
    write_json(directory / "attempt.json", record)
    print({"case": directory.parent.name, "request": directory.name, "status": record["status"],
           "decision": (record.get("proposal") or {}).get("decision"), "cost": record["cost"]}, flush=True)
    return record


def run_pair(entry, directory, request):
    case = load(entry["case_id"])
    original = (DATA / case["id"] / "input.v").read_text()
    deps = (DATA / case["id"] / "dependencies.v").read_text()
    directory.mkdir()
    (directory / "input.v").write_text(original)
    first = request(case, original, deps, directory / "shared_initial")
    attempts = {"shared_initial": first}
    branches = ["self_review", "checker_feedback"]
    if int(entry["opaque_id"].split("_")[-1]) % 2 == 0:
        branches.reverse()
    pair = {"opaque_id": entry["opaque_id"], "case_id": case["id"], "arms": {}, "attempts": attempts}
    for branch in branches:
        # Only the public discovery gate controls further inference. The audit
        # is passive and can reject a public pass without granting another call.
        if first["discovery_pass"] or first.get("transport_error"):
            chosen, path, calls = first, "shared_initial", 1
        else:
            previous = first["proposal"] or {"response_unavailable": first.get("error", first["status"])}
            observations = feedback(first["evaluation"]) if "evaluation" in first else {"status": first["status"], "error": first.get("error")}
            chosen = request(case, original, deps, directory / branch, previous=previous,
                             observations=observations if branch == "checker_feedback" else None)
            attempts[branch], path, calls = chosen, branch, 2
        pair["arms"][branch] = {"accepted": chosen["accepted"], "discovery_pass": chosen["discovery_pass"],
                                 "audit_pass": chosen["audit_pass"], "status": chosen["status"], "logical_calls": calls,
                                 "would_accept_on_discovery_but_audit_fails": chosen["discovery_pass"] and not chosen["audit_pass"],
                                 "functional_source_changed": chosen.get("functional_source_changed"),
                                 "decision": (chosen.get("proposal") or {}).get("decision"), "request_path": path}
    write_json(directory / "pair.json", pair)
    return pair


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    frozen = json.loads((DATA / "FROZEN.json").read_text())
    dataset = json.loads((DATA / "dataset.json").read_text())
    for name, expected in frozen["files"].items():
        if sha256((DATA / name).read_bytes()) != expected:
            raise ValueError("Sealed case/trace changed before inference")
    for name, expected in frozen["checker_hashes"].items():
        if sha256((ROOT / name).read_bytes()) != expected:
            raise ValueError("Checker changed after final qualification")
    root = new_run_dir("known_bug_paired", args.output)
    hashes = snapshot(root)
    for file in [Path(__file__).resolve()] + [ROOT / name for name in ("scripts/prepare_known_bug_benchmark_v2.py", "scripts/finalize_known_bug_dataset_v2.py", "rtl_agent/model_client.py", "rtl_agent/model_settings.py", "rtl_agent/budget.py", "configs/model.json", "configs/budget.json", "configs/pricing.json")]:
        name = str(file.relative_to(ROOT))
        (root / "checker_source" / name.replace("/", "__")).write_bytes(file.read_bytes())
        hashes[name] = sha256(file.read_bytes())
    protocol = {"revision": "V2 corrects v1 oracle-input scope and output-validity masking; v1 records retained and superseded", "design": "Shared initial proposal, one self-review continuation versus one discovery-feedback continuation; at most two logical model calls per arm",
                "model": MODEL, "settings": SETTINGS.to_dict(), "max_output_tokens_per_request": MAX_TOKENS,
                "run_estimated_spend_cap_usd": RUN_CAP_USD, "max_unique_paid_calls": 3 * len(dataset["cases"]), "trials_per_case": 1,
                "max_concurrent_independent_cases": 2,
                "dataset": dataset, "dataset_seal_sha256": sha256((DATA / "FROZEN.json").read_bytes()), "checker_hashes": hashes,
                "same_first_proposal_for_both_arms": True, "stop_both_if_discovery_passes_even_if_audit_fails": True,
                "audit_controls_retry_or_enters_context": False, "branch_order": "Alternate by opaque case ID parity",
                "normal_control_labels_not_passed_to_models": True, "no_manual_model_source_repair": True,
                "oracle": "Published expected traces and pre-inference corrected-control transformed audit traces. No corrected RTL loaded by candidate admission; not a reference-free behavioral oracle.",
                "scope": frozen["scope"], "costs": "Count each physical API request once. Shared initial is logically attributed to both arms and cannot be summed across arms."}
    write_json(root / "protocol.json", protocol)
    ledger = BudgetLedger()
    write_json(root / "budget_before.json", ledger.summary())
    pairs, paid = [], []
    status = "COMPLETE"
    KnownBugClient().verify_model()
    condition, active = threading.Condition(), [0]
    maximum = ledger.quote(MODEL, MAX_TOKENS)["reserved_usd"]
    def worker(entry):
        client = KnownBugClient()  # Independent API state and conversation per case.
        def request(case, source, deps, directory, **kwargs):
            with condition:
                while True:
                    spent = sum((p["cost"].get("estimated_usd") if p["cost"].get("estimated_usd") is not None else p["cost"]["reserved_usd"]) for p in paid if p["cost"])
                    if spent + maximum * (active[0] + 1) <= RUN_CAP_USD:
                        active[0] += 1
                        break
                    if not active[0]:
                        raise RuntimeError("Predeclared run budget cannot reserve another request; retain partial run")
                    condition.wait(timeout=1)
            try:
                record = request_candidate(client, case, source, deps, directory, **kwargs)
                with condition:
                    if record["api_requests"]:
                        paid.append({"path": str(directory.relative_to(root)), "api_requests": record["api_requests"], "cost": record["cost"]})
                    write_json(root / "paid_requests.json", paid)
                return record
            finally:
                with condition:
                    active[0] -= 1
                    condition.notify_all()
        return run_pair(entry, root / entry["opaque_id"], request)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, entry) for entry in dataset["cases"]]
        for future in as_completed(futures):
            try:
                pair = future.result()
                pairs.append(pair)
                write_json(root / "progress.json", {"pairs": pairs, "paid_requests": paid})
                if any(a.get("transport_error") for a in pair["attempts"].values()):
                    status = "STOPPED_ON_TRANSPORT_ERROR"
            except RuntimeError as exc:
                status = "STOPPED_ON_PREDECLARED_BUDGET"
                write_json(root / "stop_reason.json", {"error": str(exc)})
    pairs.sort(key=lambda p: p["opaque_id"])
    for name, expected in hashes.items():
        if sha256((ROOT / name).read_bytes()) != expected:
            raise ValueError("Checker changed during inference; cannot report as a frozen run")
    for name, expected in frozen["files"].items():
        if sha256((DATA / name).read_bytes()) != expected:
            raise ValueError("Dataset changed during inference")
    # Label join is for reporting only, after all model contexts have ended.
    real, controls = [], []
    for pair in pairs:
        kind = load(pair["case_id"])["kind"]
        pair["kind"] = kind
        (real if kind == "historical_defect" else controls).append(pair)
    totals = {}
    for branch in ("self_review", "checker_feedback"):
        totals[branch] = {"real_trace_passes": sum(p["arms"][branch]["accepted"] for p in real), "real_cases": len(real),
                          "normal_controls": len(controls), "normal_source_unchanged": sum(p["arms"][branch]["accepted"] and not p["arms"][branch]["functional_source_changed"] for p in controls),
                          "normal_source_edits": sum(bool(p["arms"][branch]["functional_source_changed"]) for p in controls),
                          "public_pass_rejected_by_audit": sum(p["arms"][branch]["would_accept_on_discovery_but_audit_fails"] for p in pairs),
                          "logical_model_calls": sum(p["arms"][branch]["logical_calls"] for p in pairs)}
    table = {"both_pass": 0, "self_only": 0, "feedback_only": 0, "both_fail": 0}
    for p in real:
        a, b = p["arms"]["self_review"]["accepted"], p["arms"]["checker_feedback"]["accepted"]
        table["both_pass" if a and b else "self_only" if a else "feedback_only" if b else "both_fail"] += 1
    costs = [p["cost"] for p in paid]
    report = {"status": status, "totals": totals, "paired_real_outcomes": table, "pairs": pairs, "paid_requests": paid,
              "unique_paid_calls": sum(p["api_requests"] for p in paid),
              "estimated_api_cost_usd": sum(c.get("estimated_usd") or 0 for c in costs if c),
              "unsettled_requests": sum(not c or c.get("estimated_usd") is None for c in costs),
              "checker_and_dataset_unchanged": True, "algorithmic_or_generalization_advantage_established": False,
              "scope": protocol["scope"], "golden_trace_oracle": True, "new_independent_human_study": False}
    write_json(root / "summary.json", report)
    write_json(root / "budget_after.json", ledger.summary())
    print(json.dumps({k: report[k] for k in ("status", "totals", "paired_real_outcomes", "unique_paid_calls", "estimated_api_cost_usd")}, indent=2))


if __name__ == "__main__":
    main()
