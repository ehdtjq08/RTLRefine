"""Specification-only external UART admission. Fixed source is never read."""
from __future__ import annotations

from pathlib import Path

from ..common import ROOT, sha256, write_json
from ..sequential.runner import SequentialRunner
from .contract import DATA, DISCOVERY, AUDIT, FORMAL, source_policy
from .formal import bounded
from .simulation import simulate


def evaluate(source, directory, *, runner=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "candidate.v").write_text(source)
    (directory / "contract.json").write_bytes((DATA / "contract.json").read_bytes())
    (directory / "LICENSE").write_bytes((DATA / "LICENSE").read_bytes())
    record = {"status": "POLICY_REJECTED", "accepted": False, "rtl_sha256": sha256(source.encode()),
              "discovery_simulations": [], "audit_simulations": [], "formal": [], "new_api_calls": 0,
              "fixed_reference_rtl_used": False, "synthetic_challenge": False, "independent_author": "ZipCPU / Gisselquist Technology"}
    try:
        source_policy(source)
        runner = runner or SequentialRunner(timeout=60)
        ok, detail = runner.probe(directory / "isolation")
        if not ok:
            raise RuntimeError("Isolated execution unavailable: " + detail)
        record["status"] = "EXECUTION_ERROR"
        for label, profiles in (("discovery_simulations", DISCOVERY), ("audit_simulations", AUDIT)):
            for i, profile in enumerate(profiles):
                for flow in (True, False):
                    record[label].append(simulate(source, directory / f"{label}_{i}_{int(flow)}", runner, profile, flow))
        for i, profile in enumerate(FORMAL):
            record["formal"].append(bounded(source, directory / f"formal_{i}", runner, profile))
        sim_pass = all(s["passed"] for key in ("discovery_simulations", "audit_simulations") for s in record[key])
        formal_pass = all(p["status"] == "BOUNDED_PROPERTY_PASS" for p in record["formal"])
        record["accepted"] = sim_pass and formal_pass
        record["status"] = "VERIFIED_AGAINST_SPEC_WITHIN_BOUND" if record["accepted"] else "SIMULATION_FAILED" if not sim_pass else "PROPERTY_FAILED_OR_UNPROVEN"
    except (ValueError, RuntimeError, OSError) as exc:
        record["error"] = str(exc)
    record["limitation"] = "One selected historical external UART defect, not a held-out benchmark or new discovery. Twelve finite serial/flow checks plus two bounded CTS properties. Small-divisor and computed-parity modes excluded after pre-inference maintainer-control qualification. No fixed RTL used for scoring."
    write_json(directory / "evaluation.json", record)
    return {**record, "directory": str(directory)}


def discovery_gate(record):
    return (len(record["discovery_simulations"]) == 2 * len(DISCOVERY)
            and all(s["passed"] for s in record["discovery_simulations"])
            and len(record["formal"]) == len(FORMAL)
            and all(p["status"] == "BOUNDED_PROPERTY_PASS" for p in record["formal"]))


def feedback(record):
    return {"status": "DISCOVERY_CHECKS_ONLY", "error": record.get("error"),
            "simulations": [{k: s[k] for k in ("profile", "passed", "violation_count", "first_violations")} for s in record["discovery_simulations"]],
            "properties": [{k: p[k] for k in ("status", "profile", "property", "assumptions") } for p in record["formal"]]}


def snapshot(directory):
    target = Path(directory) / "checker_source"
    target.mkdir()
    paths = sorted(Path(__file__).parent.glob("*.py")) + [ROOT / n for n in ("rtl_agent/mutations/formal.py", "rtl_agent/sequential/runner.py", "rtl_agent/tool_runner.py", "rtl_agent/tool_paths.py")]
    hashes = {}
    for path in paths:
        name = str(path.relative_to(ROOT))
        content = path.read_bytes()
        (target / name.replace("/", "__")).write_bytes(content)
        hashes[name] = sha256(content)
    write_json(Path(directory) / "checker_hashes.json", hashes)
    return hashes
