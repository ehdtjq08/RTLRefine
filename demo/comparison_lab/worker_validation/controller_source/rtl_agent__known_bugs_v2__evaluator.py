"""Admission against sealed trace values, without loading corrected RTL."""
from __future__ import annotations

import json
from pathlib import Path

from ..common import ROOT, sha256, write_json
from .cases import DATA, load, source_policy
from .engine import compile_candidate, run_trace
from .runner import BenchmarkRunner


def evaluate(case_id, source, directory, *, runner=None):
    case = load(case_id)
    base = DATA / case_id
    original = (base / "input.v").read_text()
    dependencies = (base / "dependencies.v").read_text()
    if sha256(original.encode()) != case["input_sha256"] or sha256(dependencies.encode()) != case["dependencies_sha256"]:
        raise ValueError("Pinned case source changed")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "candidate.v").write_text(source)
    write_json(directory / "case_contract.json", {k: v for k, v in case.items() if k not in ("kind",)})
    record = {"status": "POLICY_REJECTED", "accepted": False, "discovery_pass": False, "audit_pass": False,
              "rtl_sha256": sha256(source.encode()), "traces": [], "new_api_calls": 0,
              "corrected_RTL_loaded_for_scoring": False, "oracle_depends_on_corrected_trace_values": True,
              "formal_proof": False, "limit": case["oracle_scope"]}
    try:
        source_policy(source, original, case["ports"] if case["top"] == case["edited_module"] else _editable_ports(original))
        runner = runner or BenchmarkRunner()
        ok, detail = runner.probe(directory / "isolation")
        if not ok:
            raise RuntimeError("Isolation unavailable: " + detail)
        compiled = directory / "compiled"
        commands = compile_candidate(source, dependencies, case["ports"], case["clock"], case["top"], compiled, runner)
        record["commands"] = commands
        if len(commands) != 2 or commands[-1]["status"] != "PASS":
            record["status"] = "COMPILE_FAILED"
            record["error"] = (compiled / ("build.log" if len(commands) == 2 else "translate.log")).read_text()[-6000:]
        else:
            for i, item in enumerate(case["traces"]):
                trace = {**item, "stimulus": str(base / item["stimulus"]), "expected": str(base / item["expected"])}
                result = run_trace(compiled, trace, case["top"], runner)
                result["phase"] = "discovery" if i == 0 else "unexposed_audit"
                record["traces"].append(result)
                (directory / f"trace_{i}.log").write_bytes((compiled / "simulate.log").read_bytes())
            record["discovery_pass"] = record["traces"][0]["passed"]
            record["audit_pass"] = all(t["passed"] for t in record["traces"][1:])
            record["accepted"] = record["discovery_pass"] and record["audit_pass"]
            record["status"] = "ALL_SEALED_TRACES_PASS" if record["accepted"] else "AUDIT_FAILED" if record["discovery_pass"] else "DISCOVERY_TRACE_FAILED"
            for name, expected in (("candidate.v", source), ("dependencies.v", dependencies)):
                if (compiled / name).read_text() != expected:
                    raise ValueError("Worker changed source or read-only dependencies")
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        record["error"] = str(exc)
    write_json(directory / "evaluation.json", record)
    return {**record, "directory": str(directory)}


def feedback(record):
    # No audit observation, pass/fail flag, seed or audit-controlled retry.
    discovery = record["traces"][:1]
    return {"status": "DISCOVERY_ONLY", "error": record.get("error"), "traces": discovery,
            "sampling_reminder": "Cycle numbers are testbench sample indices, not internal RTL states. Outputs sampled after current inputs settle and before rising clock edge."}


def _editable_ports(source):
    # Non-top editable modules (SPI byte engine / FIFO under a wrapper) need
    # their own input names, not the enclosing controller's public pins.
    import re
    from .cases import code_only
    text = code_only(source)
    names = {}
    for declaration in re.findall(r"\binput\b(.*?)(?=\b(?:input|output|inout)\b|;|\);)", text, re.S):
        parts = declaration
        parts = re.sub(r"\[[^\]]*\]|\b(?:input|wire|reg|signed)\b", " ", parts)
        for name in re.findall(r"\b[A-Za-z_]\w*\b", parts):
            names[name] = {"direction": "input"}
    return names


def snapshot(directory):
    target = Path(directory) / "checker_source"
    target.mkdir()
    files = sorted(Path(__file__).parent.glob("*.py")) + [ROOT / n for n in ("rtl_agent/tool_runner.py", "rtl_agent/tool_paths.py", "rtl_agent/common.py")]
    hashes = {}
    for file in files:
        name = str(file.relative_to(ROOT))
        content = file.read_bytes()
        (target / name.replace("/", "__")).write_bytes(content)
        hashes[name] = sha256(content)
    write_json(Path(directory) / "checker_hashes.json", hashes)
    return hashes
