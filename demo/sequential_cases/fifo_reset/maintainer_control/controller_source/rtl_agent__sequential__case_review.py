"""One review boundary for three pinned sequential RTL contracts."""
from __future__ import annotations

import difflib
import json
import re
import zipfile
import io
from pathlib import Path

from ..common import ROOT, new_run_dir, sha256, write_json
from . import frame_case, keep_case, reset_case
from .runner import SequentialRunner

CASES = {
    "fifo_reset": {"title": "FIFO reset flush", "module": "axis_async_fifo", "assets": reset_case.ASSETS,
                   "file": "axis_async_fifo.v", "fixed": "fixed_axis_async_fifo.v", "steps": 16,
                   "contract": "Reset on either side flushes pre-reset traffic. New traffic preserves data, order, TLAST and TUSER across independent clocks."},
    "axis_keep": {"title": "AXI byte validity", "module": "axis_adapter", "assets": keep_case.ASSETS,
                  "file": "axis_adapter.v", "fixed": "fixed_axis_adapter.v", "steps": 20,
                  "contract": "S_KEEP_ENABLE=0 means every source byte is valid regardless of s_axis_tkeep. Preserve frames, byte validity and ID/DEST/USER across 8-to-8/16/32-bit paths and stalls, including enabled source masks."},
    "frame_fifo": {"title": "Frame FIFO backpressure", "module": "axis_fifo", "assets": frame_case.ASSETS,
                   "file": "axis_fifo.v", "fixed": "fixed_axis_fifo.v", "steps": 12,
                   "contract": "A four-word FRAME_FIFO with DROP_WHEN_FULL=0 must preserve eight three-byte frames and sidebands while the receiver pauses and resumes. Every frame fits individually; backpressure must prevent overwriting unread data."},
}


def get_case(case_id):
    try:
        return CASES[case_id]
    except (KeyError, TypeError):
        raise ValueError("Select one of the three supported RTL contracts") from None


def original_source(case_id):
    case = get_case(case_id)
    return (case["assets"] / case["file"]).read_text()


def source_policy(case_id, source):
    case, original = get_case(case_id), original_source(case_id)
    if not isinstance(source, str) or not 1 <= len(source.encode()) <= 24000:
        raise ValueError("Supply a UTF-8 Verilog module, at most 24 KB")
    prefix = original[:original.index(");") + 2]
    if not source.startswith(prefix):
        raise ValueError("Keep the template license, module parameters and ports byte-identical")
    if source == original:
        return source  # Untouched historical code is a valid review input.
    clean, original_clean = source, original
    marker_end = {"axis_keep": ("// bus width assertions", "\ngenerate\n"),
                  "frame_fifo": ("// check configuration", "\nlocalparam KEEP_OFFSET")}.get(case_id)
    if marker_end:
        start, end = marker_end
        guard = original[original.index(start):original.index(end)]
        if clean.count(guard) != 1:
            raise ValueError("Keep the upstream configuration assertions byte-identical")
        clean, original_clean = clean.replace(guard, ""), original_clean.replace(guard, "")
    clean = re.sub(r"/\*.*?\*/|//[^\n]*", " ", clean, flags=re.S)
    original_clean = re.sub(r"/\*.*?\*/|//[^\n]*", " ", original_clean, flags=re.S)
    directives = re.findall(r"`[^\n]*", original_clean)
    if re.findall(r"`[^\n]*", clean) != directives:
        raise ValueError("Keep the original compiler directives unchanged")
    for directive in directives:
        clean = clean.replace(directive, "", 1)
    clean = clean.replace("$clog2", "")
    if any(token in clean for token in ("$", "`", '"', "\\", "(*", "*)")):
        raise ValueError("System tasks, strings, new directives and attributes are unsupported")
    if re.search(r"\b(initial|final|task|function|force|release|bind|import|export|specify|forever|while|repeat|wait|tb|miter|golden|reference_fifo|reference_adapter|reference_frame_fifo)\b", clean):
        raise ValueError("Unsupported behavioral code or reference/testbench access")
    if re.findall(r"\bmodule\s+(\w+)", clean) != [case["module"]] or len(re.findall(r"\bendmodule\b", clean)) != 1:
        raise ValueError("Exactly the original top module is required")
    body = clean[clean.index(");") + 2:]
    if "#" in body or re.search(r"'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]*[xXzZ?]", body):
        raise ValueError("Delays and unknown literals are unsupported")
    if re.search(r"\b\w+\s*\.\s*\w+", body):
        raise ValueError("Hierarchical access is unsupported")
    return source


def simulation_summary(case_id, simulation):
    if case_id == "fifo_reset":
        return {key: simulation[key] for key in ("passed", "variant", "stale_transfers", "fresh_expected", "fresh_actual")}
    keys = ("passed", "variant", "input_transfers", "expected_bytes", "actual_bytes", "expected_frames", "actual_frames", "errors", "unstable_output")
    result = {key: simulation[key] for key in keys}
    if "bad_status" in simulation:
        result["bad_status"] = simulation["bad_status"]
    return result


def evaluate(case_id, source, directory, *, runner=None, formal_on_failure=False):
    case = get_case(case_id)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    record = {"case": case_id, "status": "POLICY_REJECTED", "rtl_sha256": sha256(source.encode()),
              "simulations": [], "bounded_comparisons": [], "new_api_calls": 0,
              "accepted": False, "scope": case["contract"], "proof_steps": case["steps"]}
    (directory / "candidate.v").write_text(source)
    (directory / "original.v").write_text(original_source(case_id))
    write_json(directory / "upstream.json", json.loads((case["assets"] / "source.json").read_text()))
    (directory / "COPYING").write_bytes((case["assets"] / "COPYING").read_bytes())
    try:
        source_policy(case_id, source)
        runner = runner or SequentialRunner(timeout=60)
        ok, detail = runner.probe(directory / "isolation")
        if not ok:
            raise RuntimeError("Isolated worker unavailable: " + detail)
        record["status"] = "TOOL_ERROR"
        if case_id == "fifo_reset":
            module, variants = reset_case, ((5, 7, 1), (7, 5, 3), (5, 11, 2))
        elif case_id == "axis_keep":
            module, variants = keep_case, keep_case.VARIANTS
        else:
            module, variants = frame_case, frame_case.VARIANTS
        for i, variant in enumerate(variants):
            record["simulations"].append(module.simulate(source, directory / f"sim_{i}", runner, variant))
        simulation_pass = all(s["passed"] for s in record["simulations"])
        if simulation_pass or formal_on_failure:
            configs = keep_case.PROOF_CONFIGS if case_id == "axis_keep" else (None,)
            for i, config in enumerate(configs):
                kwargs = {"config": config} if config is not None else {}
                record["bounded_comparisons"].append(module.bounded_compare(source, directory / f"bounded_{i}", runner, **kwargs))
        proof_pass = bool(record["bounded_comparisons"]) and all(p["status"] == "BOUNDED_PASS" for p in record["bounded_comparisons"])
        record["accepted"] = simulation_pass and proof_pass
        record["status"] = "VERIFIED_WITHIN_BOUND" if record["accepted"] else "SIMULATION_FAILED" if not simulation_pass else "FORMAL_UNPROVEN_OR_FAILED"
    except (ValueError, RuntimeError, OSError) as exc:
        record["error"] = str(exc)
    patch = "".join(difflib.unified_diff(original_source(case_id).splitlines(True), source.splitlines(True), fromfile="original.v", tofile="candidate.v"))
    (directory / "candidate.patch").write_text(patch)
    record["limitation"] = "Directed simulations plus bounded two-state comparison to a historical reference; no unbounded proof or coverage of all parameters. Fixed references are excluded from model prompts."
    write_json(directory / "review.json", record)
    return {**record, "directory": str(directory)}


def review(case_id, source):
    directory = new_run_dir("rtl_user_review")
    return evaluate(case_id, source, directory / "review")


def evidence_zip(directory):
    directory = Path(directory)
    buffer, manifest = io.BytesIO(), {}
    allowed = {".json", ".v", ".vcd", ".csv", ".ys", ".log", ".patch", ".py", ".md"}
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(directory.rglob("*")):
            if file.is_file() and (file.suffix in allowed or file.name == "COPYING") and file.name != "manifest.json":
                name, content = str(file.relative_to(directory)), file.read_bytes()
                archive.writestr(name, content)
                manifest[name] = {"sha256": sha256(content), "bytes": len(content)}
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
    return buffer.getvalue()


def symbolic_inputs(path, allowed):
    text = Path(path).read_text()
    try:
        raw = json.loads(text)
        signals = raw.get("signal", [])
    except json.JSONDecodeError:
        # Some Yosys versions emit invalid JSON escapes in internal net names.
        # Top-level input records have simple trusted names. Parse only those
        # individual JSON objects, retaining the original artifact unchanged.
        signals = []
        for line in text.splitlines():
            match = re.search(r'"name"\s*:\s*"([^"\\]+)"', line)
            if match and match.group(1) in allowed:
                signals.append(json.loads(line.strip().rstrip(",")))
    return {"signal": [s for s in signals if s.get("name") in allowed]}


def feedback(record, directory):
    result = {"status": record["status"], "error": record.get("error"),
              "simulation_observations": [simulation_summary(record["case"], s) for s in record["simulations"]],
              "bounded_results": []}
    for i, proof in enumerate(record["bounded_comparisons"]):
        value = {"status": proof["status"], "steps": proof["steps"]}
        if "config" in proof:
            value["config"] = proof["config"]
        trace = Path(directory) / f"bounded_{i}/counterexample.json"
        if proof["status"] == "COUNTEREXAMPLE" and trace.is_file():
            allowed = {"clk", "rst", "input_clk", "output_clk", "input_rst", "output_rst", "output_axis_tready", "m_axis_tready"}
            allowed.update("s_axis_" + suffix for suffix in ("tdata", "tkeep", "tvalid", "tlast", "tid", "tdest", "tuser"))
            allowed.update("input_axis_" + suffix for suffix in ("tdata", "tvalid", "tlast", "tuser"))
            try:
                value["symbolic_input_trace"] = symbolic_inputs(trace, allowed)
            except (json.JSONDecodeError, TypeError, ValueError):
                value["trace_parse_error"] = "Input witness unavailable; raw tool artifact retained"
            value["trace_scope"] = "Symbolic bounded-comparison input witness; not independently replayed. The simulation observations above are separate directed witnesses."
        result["bounded_results"].append(value)
    return result
