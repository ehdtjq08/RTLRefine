"""Budgeted NVIDIA edits for the pinned disabled-TKEEP regression."""
from __future__ import annotations

import copy
import difflib
import json
import re
from pathlib import Path

from ..common import new_run_dir, sha256, write_json
from ..model_client import NebiusClient, ModelError
from ..model_settings import ModelSettings
from .keep_case import ASSETS, PROOF_CONFIGS, STEPS, VARIANTS, bounded_compare, messages, simulate
from .repair import SCHEMA as RESET_SCHEMA
from .runner import SequentialRunner

SCHEMA = copy.deepcopy(RESET_SCHEMA)
SCHEMA["properties"]["edits"]["maxItems"] = 12
ULTRA = "nvidia/Nemotron-3-Ultra-550b-a55b"


class KeepClient(NebiusClient):
    def _request(self, endpoint, payload=None):
        if endpoint == "chat/completions" and payload is not None:
            payload = {**payload, "response_format": {"type": "json_schema", "json_schema": {
                "name": "axis_adapter_local_repair", "strict": True, "schema": SCHEMA}}}
        return super()._request(endpoint, payload)


def apply_edits(original, proposal):
    if original != (ASSETS / "axis_adapter.v").read_text():
        raise ValueError("Only the pinned adapter source is supported")
    if not isinstance(proposal, dict) or set(proposal) != {"edits", "explanation"} or not isinstance(proposal["explanation"], str):
        raise ValueError("Unexpected repair fields")
    edits = proposal["edits"]
    if not isinstance(edits, list) or not 1 <= len(edits) <= 12:
        raise ValueError("Provide one to twelve bounded local edits")
    source, applied = original, 0
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"before", "after"}:
            raise ValueError("Every edit needs before and after strings")
        before, after = edit["before"], edit["after"]
        if isinstance(before, str) and isinstance(after, str) and before == after:
            continue
        if (not isinstance(before, str) or not isinstance(after, str) or not 1 <= len(before) <= 600
                or not 1 <= len(after) <= 1200 or source.count(before) != 1):
            raise ValueError("Every before snippet must uniquely identify an original location")
        source = source.replace(before, after, 1)
        applied += 1
    if not applied:
        raise ValueError("Proposal has no edits")
    prefix = original[:original.index(");") + 2]
    if not source.startswith(prefix) or len(source.encode()) > 18000 or not source.endswith("\n`resetall\n"):
        raise ValueError("License, parameters, ports and closing directive must remain unchanged")
    # The trusted upstream parameter checks contain $error/$finish. Preserve them
    # byte-for-byte; never allow the model to add or modify executable initial code.
    guard = original[original.index("// bus width assertions"):original.index("\ngenerate\n")]
    if source.count(guard) != 1:
        raise ValueError("The upstream bus-width assertions must remain byte-identical")
    clean = source.replace(guard, "")
    clean = re.sub(r"/\*.*?\*/|//[^\n]*", " ", clean, flags=re.S)
    for directive in ("`resetall", "`timescale 1ns / 1ps", "`default_nettype none"):
        if clean.count(directive) != original.count(directive):
            raise ValueError("Directives changed")
        clean = clean.replace(directive, "")
    clean = clean.replace("$clog2", "")  # Existing constant-width arithmetic only.
    if any(token in clean for token in ("$", "`", '"', "\\", "(*", "*)")):
        raise ValueError("Added system tasks, strings, directives and attributes are forbidden")
    if re.search(r"\b(initial|final|task|function|force|release|bind|import|export|specify|forever|while|repeat|wait|tb|miter|reference_adapter|golden)\b", clean):
        raise ValueError("Unsupported behavior or testbench access")
    if re.findall(r"\bmodule\s+(\w+)", clean) != ["axis_adapter"] or len(re.findall(r"\bendmodule\b", clean)) != 1:
        raise ValueError("Only the original module is supported")
    body = clean[clean.index(");") + 2:]
    if "#" in body or re.search(r"'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]*[xXzZ?]", body):
        raise ValueError("Delays and unknown literals are forbidden")
    return source


def validate(source, directory, runner):
    simulations = [simulate(source, directory / f"sim_{i}", runner, variant) for i, variant in enumerate(VARIANTS)]
    proofs = []
    if all(s["passed"] for s in simulations):
        proofs = [bounded_compare(source, directory / f"bounded_{i}", runner, config) for i, config in enumerate(PROOF_CONFIGS)]
    status = ("VERIFIED_WITHIN_BOUND" if len(proofs) == len(PROOF_CONFIGS) and all(p["status"] == "BOUNDED_PASS" for p in proofs)
              else "FORMAL_UNPROVEN_OR_FAILED" if proofs else "SIMULATION_FAILED")
    return {"status": status, "simulations": simulations, "bounded_comparisons": proofs, "rtl_sha256": sha256(source.encode())}


def run(output=None, max_requests=1, model_id=ULTRA):
    if max_requests not in (1, 2):
        raise ValueError("One or two attempts are supported")
    settings = ModelSettings(enable_thinking=True)
    client = KeepClient(settings=settings, timeout=settings.api_timeout_seconds)
    client.model_id = model_id
    client.verify_model()
    directory = new_run_dir("axis_keep_repair", output)
    runner = SequentialRunner(timeout=60)
    ok, detail = runner.probe(directory / "isolation")
    if not ok:
        raise RuntimeError("Isolated execution unavailable: " + detail)
    original = (ASSETS / "axis_adapter.v").read_text()
    snapshots = directory / "controller_source"
    snapshots.mkdir()
    hashes = {}
    for file in sorted(Path(__file__).parent.glob("*.py")):
        content = file.read_bytes()
        (snapshots / file.name).write_bytes(content)
        hashes[file.name] = sha256(content)
    (directory / "original.v").write_text(original)
    write_json(directory / "protocol.json", {"case": "axis_adapter_disabled_keep", "model": model_id,
               "settings": settings.to_dict(), "max_requests": max_requests, "max_output_tokens": 16384,
               "proof_steps": STEPS, "proof_configs": PROOF_CONFIGS, "simulation_configs": VARIANTS,
               "source_sha256": hashes, "upstream": json.loads((ASSETS / "source.json").read_text()),
               "reference_excluded_from_prompts": True, "historical_case_not_new_discovery": True,
               "protocol_frozen_before_paid_request": True, "comparative_experiment": False})
    baseline = simulate(original, directory / "baseline", runner)
    if baseline["passed"] or baseline["actual_bytes"] != 0 or baseline["input_transfers"] != 20:
        raise ValueError("The pinned disabled-TKEEP failure did not reproduce")
    record = {"status": "NO_VERIFIED_REPAIR", "case": "axis_adapter_disabled_keep", "model": model_id,
              "baseline": baseline, "attempts": [], "accepted_rtl": None}
    feedback = None
    for number in range(1, max_requests + 1):
        attempt_dir = directory / f"attempt_{number}"
        attempt_dir.mkdir()
        prompt = messages(original, baseline, SCHEMA, feedback)
        write_json(attempt_dir / "messages.json", prompt)
        attempt, transport_error = {"attempt": number, "status": "ERROR"}, False
        try:
            response = client.generate(prompt, max_tokens=16384)
            write_json(attempt_dir / "response.json", response)
            choice = response["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ValueError("Repair response did not finish")
            proposal = json.loads(choice["message"]["content"])
            write_json(attempt_dir / "proposal.json", proposal)
            source = apply_edits(original, proposal)
            (attempt_dir / "candidate.v").write_text(source)
            attempt.update({"proposal": proposal, **validate(source, attempt_dir, runner)})
        except ModelError as exc:
            attempt["error"], transport_error = client.redact(str(exc)), True
        except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
            attempt["error"] = client.redact(type(exc).__name__ + ": " + str(exc))
        attempt["cost"] = client.last_cost
        write_json(attempt_dir / "attempt.json", attempt)
        record["attempts"].append(attempt)
        if attempt["status"] == "VERIFIED_WITHIN_BOUND":
            record.update({"status": attempt["status"], "accepted_rtl": f"attempt_{number}/candidate.v"})
            patch = "".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True), fromfile="original.v", tofile="candidate.v"))
            (directory / "accepted.patch").write_text(patch)
        write_json(directory / "repair.json", record)
        print({key: attempt.get(key) for key in ("attempt", "status", "error", "cost")}, flush=True)
        if record["accepted_rtl"] or transport_error:
            break
        feedback = {"status": attempt["status"], "error": attempt.get("error"),
                    "simulation_passed": [s["passed"] for s in attempt.get("simulations", [])],
                    "bounded_statuses": [p["status"] for p in attempt.get("bounded_comparisons", [])]}
    return {**record, "directory": str(directory)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    parser.add_argument("--max-requests", type=int, default=1)
    args = parser.parse_args()
    result = run(args.output, args.max_requests)
    print(json.dumps({key: result[key] for key in ("status", "accepted_rtl", "directory")}, indent=2))
