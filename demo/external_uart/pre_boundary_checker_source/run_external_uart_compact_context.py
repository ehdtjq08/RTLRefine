"""One compact-context development request; prior failures stay in the case report."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from rtl_agent.common import ROOT, new_run_dir, sha256, write_json
from rtl_agent.model_settings import ModelSettings
from rtl_agent.uart_external.agent import MODEL, UartClient
from rtl_agent.uart_external.contract import specification, split_source
from rtl_agent.uart_external.evaluator import evaluate, snapshot

SCHEMA = {"type": "object", "properties": {"body": {"type": "string"}, "explanation": {"type": "string"}},
          "required": ["body", "explanation"], "additionalProperties": False}


class CompactClient(UartClient):
    def _request(self, endpoint, payload=None):
        if endpoint == "chat/completions" and payload is not None:
            payload = {**payload, "response_format": {"type": "json_schema", "json_schema": {
                "name": "uart_complete_production_body", "strict": True, "schema": SCHEMA}}}
        # Call the base provider rather than the old patch-format adapter.
        from rtl_agent.model_client import NebiusClient
        return NebiusClient._request(self, endpoint, payload)


def main():
    prior = ROOT / "results/external_uart_recovery_v1_20261023"
    previous = json.loads((prior / "summary.json").read_text())
    if previous["accepted"] or previous["unique_paid_calls"] != 3:
        raise ValueError("Compact context is a separately declared development request after three recorded failures")
    old = json.loads((prior / "protocol.json").read_text())
    for relative, expected in old["qualified_checker_unchanged"].items():
        if sha256((ROOT / relative).read_bytes()) != expected:
            raise ValueError("Qualified checker changed")
    root = new_run_dir("external_uart_compact", "results/external_uart_compact_v1_20261023")
    source = (prior / "input.v").read_text()
    prefix, body, suffix = split_source(source)
    for number in (1, 2, 3):
        shutil.copytree(prior / f"attempt_{number}", root / f"attempt_{number}")
    (root / "input.v").write_text(source)
    for name in ("protocol.json", "initial_protocol.json", "initial_two_request_summary.json"):
        (root / ("previous_" + name)).write_bytes((prior / name).read_bytes())
    hashes = snapshot(root)
    script = Path(__file__).resolve()
    (root / "checker_source" / script.name).write_bytes(script.read_bytes())
    hashes[str(script.relative_to(ROOT))] = sha256(script.read_bytes())
    prior_prompt = json.loads((prior / "attempt_3/messages.json").read_text())
    # Reuse exactly the recorded discovery-only port samples, not a hand-made hint.
    observations = prior_prompt[3]["content"].split("\n", 1)[1]
    json.loads(observations)
    system = '''Check the UART production RTL against the public contract and actual external-port observations.
Return JSON with body=the COMPLETE corrected production body between the immutable
prefix and suffix, and explanation=a concise diagnosis. Body must begin with the
original clocks_per_baud wire declaration. Do not repeat the prefix or add
endmodule. The original upstream FORMAL appendix is disabled in every execution;
it is omitted from this input and restored unchanged automatically. This is a
context reduction only: executable source, contract and checker are unchanged.
Keep all existing production initial assignments exactly; add none. Keep clock,
ports, configuration meanings, ordinary serial behavior and forward progress.
No assumptions/assertions, directives, tasks, functions, hierarchy, delays,
unknown literal assignments, input drivers or additional modules. Only change
logic required by the observed contract violations. A scenario/phase number is
a testbench label, never the UART state. No corrected RTL or maintainer patch is
provided. This is a selected historical development case, not unseen accuracy.
The fixed prefix and upstream appendix will be joined with your exact returned
body bytes; no controller will repair your output. JSON schema:\n''' + json.dumps(SCHEMA)
    prompt = [{"role": "system", "content": system}, {"role": "user", "content": "Contract:\n" + json.dumps(specification()) +
              "\nImmutable prefix:\n" + prefix + "\nOriginal production body:\n" + body + "\nIndependent discovery observations:\n" + observations}]
    folder = root / "attempt_4"
    folder.mkdir()
    write_json(folder / "messages.json", prompt)
    settings = ModelSettings(enable_thinking=True)
    protocol = {"additional_requests": 1, "case_total_requests_including_all_protocols": 4, "model": MODEL,
                "settings": settings.to_dict(), "max_output_tokens": 24576, "checker_hashes": hashes,
                "original_prefix_sha256": sha256(prefix.encode()), "omitted_disabled_appendix_sha256": sha256(suffix.encode()),
                "original_production_sha256": sha256(body.encode()), "messages_sha256": sha256((folder / "messages.json").read_bytes()),
                "reason": "Third response proposed a nonmatching commented initialization. Submit complete production body, omit disabled appendix, preserve qualified scoring and all earlier failed outcomes.",
                "fixed_reference_enters_context_or_scoring": False, "audit_enters_context": False,
                "no_manual_model_output_edits": True, "previous_protocol": old, "scope": previous["scope"]}
    write_json(root / "protocol.json", protocol)
    client = CompactClient()
    client.settings = settings
    client.verify_model()
    attempt = {"number": 4, "status": "MODEL_RESPONSE_ERROR", "accepted": False}
    try:
        response = client.generate(prompt, max_tokens=24576)
        write_json(folder / "response.json", response)
        choice = response["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise ValueError("Incomplete compact-context response")
        proposal = json.loads(choice["message"]["content"])
        if not isinstance(proposal, dict) or set(proposal) != {"body", "explanation"} or not all(isinstance(v, str) for v in proposal.values()):
            raise ValueError("Unexpected complete-body schema")
        candidate = prefix + proposal["body"] + suffix
        (folder / "candidate.v").write_text(candidate)
        write_json(folder / "proposal.json", proposal)
        result = evaluate(candidate, folder / "evaluation")
        attempt.update({"proposal": proposal, "evaluation": result, "accepted": result["accepted"], "status": result["status"]})
    except (ValueError, RuntimeError, OSError, KeyError, IndexError, TypeError) as exc:
        attempt["error"] = client.redact(str(exc))
    attempt.update({"cost": client.last_cost, "api_requests": client.inference_requests})
    write_json(folder / "attempt.json", attempt)
    for relative, expected in hashes.items():
        if sha256((ROOT / relative).read_bytes()) != expected:
            raise ValueError("Scoring or context script changed during inference")
    attempts = previous["attempts"] + [attempt]
    costs = [a["cost"] for a in attempts if a["api_requests"]]
    report = {"status": "COMPLETE", "accepted": attempt["accepted"], "historical_external_cases": 1,
              "unique_paid_calls": sum(a["api_requests"] for a in attempts), "estimated_api_cost_usd": sum(c.get("estimated_usd") or 0 for c in costs if c),
              "unsettled_requests": sum(not c or c.get("estimated_usd") is None for c in costs),
              "accepted_source": "attempt_4/candidate.v" if attempt["accepted"] else None, "attempts": attempts,
              "fixed_reference_rtl_used_for_scoring": False, "manual_model_output_edits": False, "sealed_files_unchanged": True,
              "qualification": previous["qualification"], "initial_two_request_run_accepted": False,
              "development_protocols": ["two-request patch review", "one no-thinking recovery", "one compact production-body request"],
              "scope": previous["scope"]}
    write_json(root / "summary.json", report)
    print(json.dumps({k: report[k] for k in ("status", "accepted", "unique_paid_calls", "estimated_api_cost_usd", "accepted_source")}, indent=2))


if __name__ == "__main__":
    main()
