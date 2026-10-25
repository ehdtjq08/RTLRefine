"""Frozen two-request repair of a real external UART; audit cannot trigger retry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rtl_agent.common import ROOT, new_run_dir, sha256, write_json
from rtl_agent.model_client import ModelError
from rtl_agent.uart_external.agent import MODEL, SETTINGS, MAX_TOKENS, UartClient, messages, parse_proposal
from rtl_agent.uart_external.contract import DATA, VENDOR, DISCOVERY, AUDIT, FORMAL
from rtl_agent.uart_external.evaluator import evaluate, snapshot, discovery_gate, feedback


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qualification", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    qualification_path = Path(args.qualification)
    qualification = json.loads(qualification_path.read_text())
    if not qualification["qualified"]:
        raise ValueError("Both original failure and independent maintainer control must qualify first")
    for name, expected in qualification["checker_hashes"].items():
        if sha256((ROOT / name).read_bytes()) != expected:
            raise ValueError("Checker changed since qualification")
    for name, expected in qualification["contract_hashes"].items():
        if sha256((DATA / name).read_bytes()) != expected:
            raise ValueError("Contract changed since qualification")
    source = (VENDOR / "buggy/txuart.v").read_text()
    if sha256(source.encode()) != qualification["historical_source_sha256"]:
        raise ValueError("Original changed since qualification")
    root = new_run_dir("external_uart_repair", args.output)
    hashes = snapshot(root)
    script = Path(__file__).resolve()
    (root / "checker_source" / script.name).write_bytes(script.read_bytes())
    hashes[str(script.relative_to(ROOT))] = sha256(script.read_bytes())
    sealed = {str(p.relative_to(ROOT)): sha256(p.read_bytes()) for p in sorted(DATA.iterdir()) if p.is_file()}
    for relative in ("rtl_agent/model_client.py", "rtl_agent/model_settings.py", "rtl_agent/budget.py", "configs/budget.json", "configs/pricing.json"):
        sealed[relative] = sha256((ROOT / relative).read_bytes())
    (root / "input.v").write_text(source)
    protocol = {"model": MODEL, "settings": SETTINGS.to_dict(), "max_output_tokens": MAX_TOKENS, "max_requests": 2,
                "original_sha256": sha256(source.encode()), "qualification_sha256": sha256(qualification_path.read_bytes()),
                "checker_hashes": hashes, "sealed_inputs": sealed, "discovery_profiles": DISCOVERY, "unexposed_audit_profiles": AUDIT,
                "formal_profiles": FORMAL, "fixed_reference_rtl_used_for_scoring": False, "synthetic": False,
                "maintainer_fix_in_model_context": False, "audit_controls_retries": False,
                "scope": "One selected public historical UART bug from another author. Training contamination cannot be excluded; not held-out accuracy or algorithm superiority."}
    write_json(root / "protocol.json", protocol)
    client = UartClient()
    client.verify_model()
    attempts, previous, observations = [], None, None
    for number in (1, 2):
        folder = root / f"attempt_{number}"
        folder.mkdir()
        prompt = messages(source, previous=previous, observations=observations)
        encoded = json.dumps(prompt)
        for hidden in ("07e4c47166f0407c276bee571900ed2f9df06bad", "maintainer_fixed", "7403", "8501", "9601"):
            if hidden in encoded:
                raise ValueError("Hidden control/audit information entered prompt")
        write_json(folder / "messages.json", prompt)
        before = client.inference_requests
        attempt = {"number": number, "status": "MODEL_RESPONSE_ERROR", "accepted": False}
        transport_error = False
        try:
            response = client.generate(prompt, max_tokens=MAX_TOKENS)
            write_json(folder / "response.json", response)
            proposal, candidate = parse_proposal(response, source)
            write_json(folder / "proposal.json", proposal)
            (folder / "candidate.v").write_text(candidate)
            result = evaluate(candidate, folder / "evaluation")
            attempt.update({"proposal": proposal, "evaluation": result, "accepted": result["accepted"], "status": result["status"],
                            "discovery_gate_passed": discovery_gate(result)})
        except ModelError as exc:
            attempt["error"], transport_error = client.redact(str(exc)), True
        except (ValueError, OSError, KeyError, IndexError, TypeError) as exc:
            attempt["error"] = client.redact(type(exc).__name__ + ": " + str(exc))
        attempt.update({"cost": client.last_cost, "api_requests": client.inference_requests - before})
        attempts.append(attempt)
        write_json(folder / "attempt.json", attempt)
        print({"attempt": number, "status": attempt["status"], "accepted": attempt["accepted"], "cost": attempt["cost"]}, flush=True)
        if attempt.get("discovery_gate_passed") or transport_error:
            break
        previous = attempt.get("proposal") or {"response_error": attempt.get("error", attempt["status"])}
        observations = feedback(attempt["evaluation"]) if "evaluation" in attempt else {"status": attempt["status"], "error": attempt.get("error")}
    for relative, expected in {**hashes, **sealed}.items():
        if sha256((ROOT / relative).read_bytes()) != expected:
            raise ValueError("Sealed checker or input changed during inference")
    costs = [a["cost"] for a in attempts if a["api_requests"]]
    report = {"status": "COMPLETE", "accepted": attempts[-1]["accepted"], "historical_external_cases": 1,
              "unique_paid_calls": sum(a["api_requests"] for a in attempts), "estimated_api_cost_usd": sum(c.get("estimated_usd") or 0 for c in costs if c),
              "unsettled_requests": sum(not c or c.get("estimated_usd") is None for c in costs),
              "accepted_source": f"attempt_{len(attempts)}/candidate.v" if attempts[-1]["accepted"] else None,
              "attempts": attempts, "fixed_reference_rtl_used_for_scoring": False, "manual_model_output_edits": False,
              "sealed_files_unchanged": True, "qualification": str(qualification_path), "scope": protocol["scope"]}
    write_json(root / "summary.json", report)
    print(json.dumps({k: report[k] for k in ("status", "accepted", "unique_paid_calls", "estimated_api_cost_usd", "accepted_source")}, indent=2))


if __name__ == "__main__":
    main()
