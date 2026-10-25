"""Budgeted NVIDIA local RTL edits; evaluation-only upstream fix stays private."""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from ..common import ROOT, new_run_dir, sha256, write_json
from ..model_client import NebiusClient, ModelError
from ..model_settings import ModelSettings
from .reset_case import ASSETS, bounded_compare, simulate
from .runner import SequentialRunner

SCHEMA = {"type": "object", "properties": {
    "edits": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
        "type": "object", "properties": {"before": {"type": "string"}, "after": {"type": "string"}},
        "required": ["before", "after"], "additionalProperties": False}},
    "explanation": {"type": "string"}}, "required": ["edits", "explanation"], "additionalProperties": False}


class RepairClient(NebiusClient):
    def _request(self, endpoint, payload=None):
        if endpoint == "chat/completions" and payload is not None:
            payload = {**payload, "response_format": {"type": "json_schema", "json_schema": {
                "name": "local_verilog_repair", "strict": True, "schema": SCHEMA}}}
        return super()._request(endpoint, payload)


def apply_edits(original, proposal):
    if not isinstance(proposal, dict) or set(proposal) != {"edits", "explanation"} or not isinstance(proposal["explanation"], str):
        raise ValueError("Unexpected repair fields")
    edits = proposal["edits"]
    if not isinstance(edits, list) or not 1 <= len(edits) <= 4:
        raise ValueError("Provide one to four bounded local edits")
    source = original
    applied = 0
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"before", "after"}:
            raise ValueError("Every edit needs before and after strings")
        before, after = edit["before"], edit["after"]
        if isinstance(before, str) and isinstance(after, str) and before == after:
            continue  # A no-op changes no code; retain it in the raw proposal.
        if (not isinstance(before, str) or not isinstance(after, str) or not 1 <= len(before) <= 600
                or not 1 <= len(after) <= 1200 or before == after or source.count(before) != 1):
            raise ValueError("Each before snippet must identify exactly one original location")
        source = source.replace(before, after, 1)
        applied += 1
    if not applied:
        raise ValueError("Proposal contains no functional edits")
    prefix = original[:original.index(");") + 2]
    if not source.startswith(prefix) or len(source.encode()) > 12000:
        raise ValueError("License, module parameters, and ports must remain byte-identical")
    clean = re.sub(r"/\*.*?\*/|//[^\n]*", " ", source, flags=re.S)
    clean = clean.replace("`timescale 1ns / 1ps", "")
    if any(token in clean for token in ("$", "`", '"', "\\", "(*", "*)")):
        raise ValueError("System tasks, directives, strings, and synthesis attributes are forbidden")
    if re.search(r"\b(initial|final|task|function|force|release|bind|import|export|specify|forever|while|repeat|wait|tb|miter|reference_fifo)\b", clean):
        raise ValueError("Unsupported behavioral or testbench access")
    if re.findall(r"\bmodule\s+(\w+)", clean) != ["axis_async_fifo"] or len(re.findall(r"\bendmodule\b", clean)) != 1:
        raise ValueError("Exactly the original module is required")
    body = clean[clean.index(");") + 2:]
    if "#" in body or re.search(r"'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]*[xXzZ?]", body):
        raise ValueError("Timing delays and unknown literals are forbidden")
    return source


def messages(original, baseline, feedback=None):
    system = """Repair this Verilog 2001 AXI-stream FIFO with small local edits.
Keep the license header, module parameters, ports, normal throughput, payload,
ordering and sideband behavior. A reset on either side must flush pre-reset
traffic. Subsequent new traffic must still work. Do not tie off outputs or inspect
the testbench. No system tasks, extra modules, includes, strings or timing delays.
Return one to four local before/after replacements. Each before string must be
an exact, uniquely occurring snippet from the supplied ORIGINAL source, including
whitespace. Use small snippets around the changed logic. Do not copy the entire
module. You receive no reference implementation or known patch. The controller
will independently simulate and compare against an evaluation-only reference.
Required JSON output schema:\n""" + json.dumps(SCHEMA)
    summary = {"stale_after_reset": baseline["stale_transfers"], "fresh_expected": baseline["fresh_expected"],
               "fresh_actual": baseline["fresh_actual"], "test_clock_half_periods_ns": [5, 7]}
    user = "Original RTL:\n" + original + "\nObserved failure (independent Icarus testbench):\n" + json.dumps(summary)
    if feedback is not None:
        user += "\nPrevious proposal feedback; propose edits against the same original source:\n" + json.dumps(feedback)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def run(output=None, max_requests=2, thinking=False, model_id=None):
    if max_requests not in (1, 2):
        raise ValueError("One or two paid attempts are supported")
    settings = ModelSettings(enable_thinking=thinking)
    client = RepairClient(settings=settings, timeout=settings.api_timeout_seconds)
    if model_id is not None:
        client.model_id = model_id
    client.verify_model()
    directory = new_run_dir("axis_reset_repair", output)
    runner = SequentialRunner(timeout=60)
    ready, detail = runner.probe(directory / "isolation")
    if not ready:
        raise RuntimeError("Isolated execution is unavailable: " + detail)
    original = (ASSETS / "axis_async_fifo.v").read_text()
    source_snapshot = directory / "controller_source"
    source_snapshot.mkdir()
    hashes = {}
    for file in sorted(Path(__file__).parent.glob("*.py")):
        content = file.read_bytes()
        (source_snapshot / file.name).write_bytes(content)
        hashes[file.name] = sha256(content)
    (directory / "original.v").write_text(original)
    write_json(directory / "protocol.json", {"model": client.model_id, "settings": settings.to_dict(),
              "max_requests": max_requests, "max_output_tokens": 8192, "proof_steps": 16,
              "source_sha256": hashes, "upstream": json.loads((ASSETS / "source.json").read_text()),
              "reference_excluded_from_prompts": True, "historical_case_not_new_discovery": True,
              "development_note": "Default disables extended reasoning after two earlier 8192-token reasoning-only truncations; earlier outcomes are retained"})
    baseline = simulate(original, directory / "baseline", runner)
    if baseline["passed"] or not baseline["stale_transfers"]:
        raise ValueError("Historical reset bug did not independently reproduce")
    attempts, feedback = [], None
    record = {"status": "NO_VERIFIED_REPAIR", "model": client.model_id, "baseline": baseline,
              "attempts": attempts, "accepted_rtl": None}
    for number in range(1, max_requests + 1):
        attempt_dir = directory / f"attempt_{number}"
        attempt_dir.mkdir()
        prompt = messages(original, baseline, feedback)
        write_json(attempt_dir / "messages.json", prompt)
        attempt = {"attempt": number, "status": "ERROR"}
        transport_error = False
        try:
            response = client.generate(prompt, max_tokens=8192)
            write_json(attempt_dir / "response.json", response)
            choice = response["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ValueError("Repair response did not finish")
            proposal = json.loads(choice["message"]["content"])
            write_json(attempt_dir / "proposal.json", proposal)
            source = apply_edits(original, proposal)
            (attempt_dir / "candidate.v").write_text(source)
            attempt["rtl_sha256"] = sha256(source.encode())
            attempt["proposal"] = proposal
            simulations = [simulate(source, attempt_dir / f"sim_{i}", runner, variant) for i, variant in enumerate(
                ((5, 7, 1), (7, 5, 3), (5, 11, 2)))]
            attempt["simulations"] = simulations
            if all(result["passed"] for result in simulations):
                proof = bounded_compare(source, attempt_dir / "bounded", runner, 16)
                attempt["bounded"] = proof
                attempt["status"] = "VERIFIED_WITHIN_BOUND" if proof["status"] == "BOUNDED_PASS" else "FORMAL_UNPROVEN_OR_FAILED"
            else:
                attempt["status"] = "SIMULATION_FAILED"
        except ModelError as exc:
            attempt["error"] = client.redact(str(exc))
            transport_error = True
        except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
            attempt["error"] = client.redact(type(exc).__name__ + ": " + str(exc))
        attempt["cost"] = client.last_cost
        write_json(attempt_dir / "attempt.json", attempt)
        attempts.append(attempt)
        if attempt["status"] == "VERIFIED_WITHIN_BOUND":
            record["status"] = attempt["status"]
            record["accepted_rtl"] = f"attempt_{number}/candidate.v"
            patch = "".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
                                               fromfile="original.v", tofile="candidate.v"))
            (directory / "accepted.patch").write_text(patch)
        write_json(directory / "repair.json", record)
        print({"attempt": number, "status": attempt["status"], "error": attempt.get("error"), "cost": attempt["cost"]}, flush=True)
        if record["accepted_rtl"] or transport_error:
            break
        feedback = {"status": attempt["status"], "error": attempt.get("error"),
                    "simulation_passed": [result["passed"] for result in attempt.get("simulations", [])]}
    return {**record, "directory": str(directory)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    parser.add_argument("--max-requests", type=int, default=2)
    parser.add_argument("--thinking", action="store_true")
    parser.add_argument("--model")
    args = parser.parse_args()
    result = run(args.output, args.max_requests, args.thinking, args.model)
    print(json.dumps({key: result[key] for key in ("status", "accepted_rtl", "directory")}, indent=2))
