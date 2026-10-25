"""One separately declared recovery request; retain both failed initial requests."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from rtl_agent.common import ROOT, new_run_dir, sha256, write_json
from rtl_agent.model_client import ModelError
from rtl_agent.model_settings import ModelSettings
from rtl_agent.uart_external.agent import MODEL, MAX_TOKENS, UartClient, messages, parse_proposal
from rtl_agent.uart_external.evaluator import evaluate, feedback, snapshot


def main():
    initial = ROOT / "results/external_uart_repair_v1_20261023"
    original_report = json.loads((initial / "summary.json").read_text())
    old_protocol = json.loads((initial / "protocol.json").read_text())
    if original_report["accepted"] or original_report["unique_paid_calls"] != 2:
        raise ValueError("This recovery is only for the recorded, failed two-request development run")
    for relative, expected in {**old_protocol["checker_hashes"], **old_protocol["sealed_inputs"]}.items():
        if sha256((ROOT / relative).read_bytes()) != expected:
            raise ValueError("Do not change the qualified checker during recovery")
    root = new_run_dir("external_uart_recovery", "results/external_uart_recovery_v1_20261023")
    source = (initial / "input.v").read_text()
    (root / "input.v").write_text(source)
    for number in (1, 2):
        shutil.copytree(initial / f"attempt_{number}", root / f"attempt_{number}")
    (root / "initial_protocol.json").write_bytes((initial / "protocol.json").read_bytes())
    (root / "initial_two_request_summary.json").write_bytes((initial / "summary.json").read_bytes())
    hashes = snapshot(root)
    script = Path(__file__).resolve()
    (root / "checker_source" / script.name).write_bytes(script.read_bytes())
    hashes[str(script.relative_to(ROOT))] = sha256(script.read_bytes())
    first = original_report["attempts"][0]
    observations = feedback(first["evaluation"])
    observations["phase_field_meaning"] = "Testbench scenario identifier, never an internal DUT state or UART bit index. 3=first post-BREAK recovery with receiver continuously blocked; 8=second post-BREAK recovery with receiver blocked."
    observations["external_port_windows"] = []
    for simulation in first["evaluation"]["discovery_simulations"]:
        if simulation["passed"]:
            continue
        profile = simulation["profile"]
        # Choose from discovery only; the unexposed audit remains unused.
        index = next(i for i, p in enumerate(old_protocol["discovery_profiles"]) if p[0] == profile["baud_cycles"])
        directory = initial / f"attempt_1/evaluation/discovery_simulations_{index}_1"
        rows = json.loads((directory / "observations.json").read_text())
        cycle = simulation["first_violations"][0]["cycle"]
        observations["external_port_windows"].append({"profile": profile, "samples": [r for r in rows if cycle - 5 <= r["cycle"] <= cycle + 8]})
    prompt = messages(source, previous=first["proposal"], observations=observations)
    prompt.append({"role": "user", "content": "The previous feedback response exhausted its output limit without a completed JSON proposal. Return only the required JSON patch. Scenario identifiers in observations are not DUT states. Use the sampled public input/output ports to assess the contract; preserve the original license and interface."})
    settings = ModelSettings(enable_thinking=False)
    folder = root / "attempt_3"
    folder.mkdir()
    write_json(folder / "messages.json", prompt)
    protocol = {"additional_requests": 1, "total_requests_in_case_including_initial_run": 3, "model": MODEL,
                "settings": settings.to_dict(), "max_output_tokens": MAX_TOKENS, "qualified_checker_unchanged": hashes,
                "prior_protocol": old_protocol, "messages_sha256": sha256((folder / "messages.json").read_bytes()),
                "reason_for_separate_protocol": "Initial keep was incorrect; second response hit token limit. One no-thinking format recovery with explicit external-port discovery samples and clarified testbench scenario labels.",
                "audit_results_enter_context": False, "fixed_source_enters_context_or_scoring": False,
                "no_model_output_hand_editing": True, "scope": old_protocol["scope"]}
    write_json(root / "protocol.json", protocol)
    client = UartClient()
    client.settings = settings
    client.verify_model()
    attempt = {"number": 3, "status": "MODEL_RESPONSE_ERROR", "accepted": False}
    try:
        response = client.generate(prompt, max_tokens=MAX_TOKENS)
        write_json(folder / "response.json", response)
        proposal, candidate = parse_proposal(response, source)
        write_json(folder / "proposal.json", proposal)
        (folder / "candidate.v").write_text(candidate)
        result = evaluate(candidate, folder / "evaluation")
        attempt.update({"proposal": proposal, "evaluation": result, "accepted": result["accepted"], "status": result["status"]})
    except (ModelError, ValueError, RuntimeError, OSError, KeyError, IndexError, TypeError) as exc:
        attempt["error"] = client.redact(str(exc))
    attempt.update({"cost": client.last_cost, "api_requests": client.inference_requests})
    write_json(folder / "attempt.json", attempt)
    for relative, expected in {**hashes, **old_protocol["sealed_inputs"]}.items():
        if sha256((ROOT / relative).read_bytes()) != expected:
            raise ValueError("Sealed checker changed during recovery")
    attempts = original_report["attempts"] + [attempt]
    costs = [a["cost"] for a in attempts if a["api_requests"]]
    report = {"status": "COMPLETE", "accepted": attempt["accepted"], "historical_external_cases": 1,
              "unique_paid_calls": sum(a["api_requests"] for a in attempts), "estimated_api_cost_usd": sum(c.get("estimated_usd") or 0 for c in costs if c),
              "unsettled_requests": sum(not c or c.get("estimated_usd") is None for c in costs),
              "accepted_source": "attempt_3/candidate.v" if attempt["accepted"] else None,
              "attempts": attempts, "fixed_reference_rtl_used_for_scoring": False, "manual_model_output_edits": False,
              "sealed_files_unchanged": True, "qualification": original_report["qualification"],
              "initial_two_request_run_accepted": False, "separate_one_request_recovery": True,
              "scope": old_protocol["scope"]}
    write_json(root / "summary.json", report)
    print(json.dumps({k: report[k] for k in ("status", "accepted", "unique_paid_calls", "estimated_api_cost_usd", "accepted_source")}, indent=2))


if __name__ == "__main__":
    main()
