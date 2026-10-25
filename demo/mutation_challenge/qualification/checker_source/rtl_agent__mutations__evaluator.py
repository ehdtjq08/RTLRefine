"""Reference-free admission using interface observations and public properties."""
from __future__ import annotations

import json
from pathlib import Path

from ..common import ROOT, sha256, write_json
from ..sequential.runner import SequentialRunner
from .contract import DATA, AUDIT, DISCOVERY, FORMAL_PROFILES, source_policy
from .formal import bounded
from .simulation import simulate


def evaluate(source, directory, *, runner=None, formal_on_failure=True):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "candidate.v").write_text(source)
    (directory / "contract.json").write_bytes((DATA / "contract.json").read_bytes())
    (directory / "COPYING").write_bytes((DATA / "COPYING").read_bytes())
    record = {"status": "POLICY_REJECTED", "accepted": False, "rtl_sha256": sha256(source.encode()),
              "discovery_simulations": [], "audit_simulations": [], "formal": [], "new_api_calls": 0,
              "fixed_reference_rtl_used": False, "synthetic_challenge": True}
    try:
        source_policy(source)
        runner = runner or SequentialRunner(timeout=60)
        ok, detail = runner.probe(directory / "isolation")
        if not ok:
            raise RuntimeError("Isolated execution unavailable: " + detail)
        record["status"] = "EXECUTION_ERROR"
        for label, profiles in (("discovery_simulations", DISCOVERY), ("audit_simulations", AUDIT)):
            for i, profile in enumerate(profiles):
                record[label].append(simulate(source, directory / f"{label}_{i}", runner, profile))
        simulation_pass = all(s["passed"] for label in ("discovery_simulations", "audit_simulations") for s in record[label])
        if simulation_pass or formal_on_failure:
            for i, profile in enumerate(FORMAL_PROFILES):
                record["formal"].append(bounded(source, directory / f"formal_{i}", runner, profile))
        proof_pass = len(record["formal"]) == len(FORMAL_PROFILES) and all(p["status"] == "BOUNDED_PROPERTY_PASS" for p in record["formal"])
        record["accepted"] = simulation_pass and proof_pass
        record["status"] = "VERIFIED_AGAINST_SPEC_WITHIN_BOUND" if record["accepted"] else "SIMULATION_FAILED" if not simulation_pass else "PROPERTY_FAILED_OR_UNPROVEN"
    except (ValueError, RuntimeError, OSError) as exc:
        record["error"] = str(exc)
    record["limitation"] = "Synthetic faults; six finite directed/random regressions and 16/12-step two-state checks at fixed profiles. Not real-world defect discovery, all-parameter correctness or an unbounded proof. No clean RTL is read by this evaluator."
    write_json(directory / "evaluation.json", record)
    return {**record, "directory": str(directory)}


def feedback(record):
    # Audit seeds/results never enter the repair context.
    result = {"status": "DISCOVERY_CHECKS", "error": record.get("error"), "observations": [], "properties": []}
    for simulation in record["discovery_simulations"]:
        result["observations"].append({key: simulation[key] for key in ("passed", "profile", "violation_count", "first_violations")})
    for proof in record["formal"]:
        value = {key: proof[key] for key in ("status", "profile", "assumptions", "initial_state", "properties")}
        if "public_trace" in proof:
            value["input_and_interface_witness"] = proof["public_trace"]
        if "replay" in proof:
            value["replay_status"] = proof["replay"]["status"]
        result["properties"].append(value)
    return result


def discovery_gate(record):
    return (len(record["discovery_simulations"]) == len(DISCOVERY)
            and all(s["passed"] for s in record["discovery_simulations"])
            and len(record["formal"]) == len(FORMAL_PROFILES)
            and all(p["status"] == "BOUNDED_PROPERTY_PASS" for p in record["formal"]))


def snapshot(directory):
    target = Path(directory) / "checker_source"
    target.mkdir()
    hashes = {}
    files = sorted(Path(__file__).parent.glob("*.py")) + [ROOT / "rtl_agent/sequential/runner.py", ROOT / "rtl_agent/tool_runner.py", ROOT / "rtl_agent/tool_paths.py"]
    for file in files:
        name = str(file.relative_to(ROOT)).replace("/", "__")
        content = file.read_bytes()
        (target / name).write_bytes(content)
        hashes[str(file.relative_to(ROOT))] = sha256(content)
    write_json(Path(directory) / "checker_hashes.json", hashes)
    return hashes
