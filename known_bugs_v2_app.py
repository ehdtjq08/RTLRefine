"""Known public RTL bugs: recorded equal-budget comparison and editable checks."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import zipfile

import streamlit as st

from rtl_agent.common import ROOT, new_run_dir, sha256, write_json
from rtl_agent.known_bugs_v2.cases import DATA, load
from rtl_agent.known_bugs_v2.evaluator import evaluate, feedback, snapshot
from rtl_agent.known_bugs_v2.runner import BenchmarkRunner
from rtl_agent.known_bugs_v2.agent import KnownBugClient
from rtl_agent.tool_paths import find_tool
from scripts.run_known_bug_comparison_v2 import request_candidate
from workspace_service import execution_slot

DEMO = ROOT / "demo/known_bug_comparison_v2"


def ready():
    missing = [name for name in ("yosys", "verilator", "g++", "make", "bwrap", "prlimit") if not find_tool(name)]
    if missing:
        return False, "Recorded evidence is available. Fresh checks need: " + ", ".join(missing)
    version = BenchmarkRunner.version("verilator") or ""
    if not version.startswith("Verilator 4.038 "):
        return False, "These recorded profiles use Verilator 4.038. Install the pinned native tools before running fresh checks."
    return True, ""


def fresh_check(case_id, source):
    root = new_run_dir("known_bug_workspace")
    snapshot(root)
    with execution_slot():
        return evaluate(case_id, source, root / "evaluation")


def live_repair(case_id, source, checked):
    if checked["rtl_sha256"] != sha256(source.encode()) or checked["discovery_pass"]:
        raise ValueError("Check the exact current discovery-failing source first")
    root = new_run_dir("known_bug_workspace_nvidia")
    snapshot(root)
    client = KnownBugClient()
    client.verify_model()
    case = load(case_id)
    dependencies = (DATA / case_id / "dependencies.v").read_text()
    with execution_slot():
        result = request_candidate(client, case, source, dependencies, root / "request",
                                   previous={"decision": "keep", "edits": [], "explanation": "Current designer-submitted source"},
                                   observations=feedback(checked))
    write_json(root / "model_run.json", result)
    return {**result, "directory": str(root / "request")}


@st.cache_data(show_spinner=False, max_entries=6)
def evidence(case_id, record_dir):
    root = Path(record_dir)
    files = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "obj_dir" in path.parts or path.suffix in (".o", ".a", ".vvp"):
            continue
        if "compiled" in path.parts and path.name in ("stimulus.hex", "expected.hex"):
            continue
        if path.suffix in (".json", ".v", ".cpp", ".log", ".py", ".md", ".patch"):
            files["record/" + str(path.relative_to(root))] = path.read_bytes()
    for path in sorted((DATA / case_id).rglob("*")):
        if path.is_file():
            files["sealed_case/" + str(path.relative_to(DATA / case_id))] = path.read_bytes()
    for parent in (root, *list(root.parents)[:3]):
        if (parent / "checker_source").is_dir():
            for path in sorted((parent / "checker_source").glob("*")):
                if path.is_file():
                    files["checker_source/" + path.name] = path.read_bytes()
            break
    notice = DEMO / "MODIFICATIONS.md"
    if notice.exists():
        files["MODIFICATIONS.md"] = notice.read_bytes()
    artifact_license = DEMO / "ARTIFACT-LICENSE-BSD-3-Clause.txt"
    if artifact_license.exists():
        files["ARTIFACT-LICENSE-BSD-3-Clause.txt"] = artifact_license.read_bytes()
    manifest = {name: {"sha256": sha256(data), "bytes": len(data)} for name, data in files.items()}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
    return buffer.getvalue()


def render_check(result, directory, key):
    directory = Path(directory)
    source = (directory / "candidate.v").read_bytes()
    if sha256(source) != result["rtl_sha256"]:
        raise ValueError("Source no longer matches the recorded check")
    st.markdown("**" + ("ALL SEALED TRACES PASS" if result["accepted"] else "NOT ACCEPTED · " + result["status"]) + "**")
    a, b, c = st.columns(3)
    a.metric("Published discovery trace", "Pass" if result["discovery_pass"] else "Fail")
    b.metric("Additional audit traces", f"{sum(t['passed'] for t in result['traces'][1:])}/2")
    c.metric("Formal correctness proof", "No")
    st.caption("Checked source SHA-256: " + result["rtl_sha256"])
    st.caption("Fixed-profile, two-state, cycle-exact regression agreement. Audit expected values were captured from a corrected research control before inference. This is a golden-trace oracle, not an independent behavioral proof.")
    if result.get("error"):
        with st.expander("Compilation / source-policy details"):
            st.code(result["error"])
    if result["traces"]:
        st.table([{"Trace": t["phase"], "Cycles": t["cycles"], "Compared port values": t["comparisons"],
                   "Mismatches": t["mismatch_count"], "Pass": t["passed"]} for t in result["traces"]])
        chosen = next((t for t in result["traces"] if not t["passed"]), result["traces"][0])
        if chosen["first_mismatches"]:
            st.write("First observed public-port mismatches")
            st.json(chosen["first_mismatches"][:4])
            with st.expander("Sampled public input windows"):
                st.json(chosen["input_windows"][:2])
    if result["accepted"]:
        label = "Download current checked RTL" if key.startswith("fresh_") else "Download checked RTL"
        st.download_button(label, source, file_name="checked_candidate.v", key="rtl_" + key)


def main():
    st.set_page_config(page_title="RTLRefine · Known-bug comparison", layout="wide")
    st.caption("RTLREFINE · PUBLIC HISTORICAL BUGS · EQUAL MODEL-CALL CAPS")
    st.title("A fair test on known RTL bugs.")
    st.caption("V2 · supported input domains · valid-qualified outputs · independent frame-count oracle guard")
    st.write("Compare NVIDIA self-review with execution feedback on a preselected, frozen set of public RTL defects and healthy controls.")
    path = DEMO / "run/summary.json"
    if not path.exists():
        st.info("The fixed-cohort model comparison is running. The complete result will appear after every case finishes and the source/trace seals are checked.")
        return
    summary = json.loads(path.read_text())
    if summary["status"] != "COMPLETE":
        st.warning("Partial experiment · " + summary["status"])
    totals = summary["totals"]
    a, b, c = st.columns(3)
    a.metric("Self-review trace passes", f"{totals['self_review']['real_trace_passes']}/{totals['self_review']['real_cases']}")
    b.metric("Execution-feedback trace passes", f"{totals['checker_feedback']['real_trace_passes']}/{totals['checker_feedback']['real_cases']}")
    c.metric("Unique NVIDIA calls", summary["unique_paid_calls"])
    st.caption(f"Estimated model cost ${summary['estimated_api_cost_usd']:.4f}. Each pair shares the first proposal and has a cap of two logical calls per arm. Branch order alternates; one trial per case. Additional audit results never enter the model context or grant another request.")
    st.info("Known historical research-artifact versions, not newly discovered or unseen bugs. This comparison uses golden-trace regression oracles. It is separate from the authored queue specification challenge and the earlier three-case comparison.")
    view = st.radio("Benchmark view", ["Complete comparison", "Inspect and check a candidate", "Oracle validity"], horizontal=True)
    if view == "Oracle validity":
        st.subheader("Supported oracle domain")
        st.write("V2 restricts frame-length masks to contiguous low-order ones; checks length values only when valid; ignores invalid stream payloads and implementation-specific SPI debug output; changes only FIFO payload data in SPI audit inputs. An independent Python count model qualifies frame-length expected values before inference.")
        with st.expander("V1 development correction"):
            st.warning("The v1 interpretation of a harmful normal-code rewrite was withdrawn: the generated TKEEP masks exceeded the reference implementation\'s supported domain. A model popcount change was a legitimate improvement, not demonstrated damage.")
            st.caption("Both the original v1 data and this separately frozen v2 study are retained. Results are not pooled. No source edit alone is called harmful without a valid behavioral failure.")
        return
    if view == "Complete comparison":
        st.table([{"Case": p["opaque_id"], "Artifact scenario": p["case_id"],
                   "Self-review": p["arms"]["self_review"]["status"], "Execution feedback": p["arms"]["checker_feedback"]["status"]}
                  for p in summary["pairs"] if p["kind"] == "historical_defect"])
        st.write("Reference controls and additional-trace agreement")
        st.table([{"Method": name, "Control source unchanged": f"{row['normal_source_unchanged']}/{row['normal_controls']}",
                   "Control traces passed": f"{sum(p['kind']=='normal_control' and p['arms'][name]['accepted'] for p in summary['pairs'])}/{row['normal_controls']}",
                   "Control source edits": row["normal_source_edits"],
                   "Public passes rejected by audit": row["public_pass_rejected_by_audit"]} for name, row in totals.items()])
        with st.expander("Paired outcomes and protocol scope"):
            st.json(summary["paired_real_outcomes"])
            st.json(json.loads((DEMO / "run/protocol.json").read_text()))
        st.caption("A small, selected development cohort cannot establish general repair accuracy, human productivity gains or superiority over other RTL research systems. Public-source training contamination is possible. All failures remain in the evidence.")
        st.markdown("[Inspect the earlier separate historical comparison](/comparison)")
        return
    pair = st.selectbox("Known-bug candidate", summary["pairs"], format_func=lambda p: p["opaque_id"] + " · " + p["case_id"])
    case_id = pair["case_id"]
    st.caption("Evaluation label: " + pair["kind"])
    branch = st.radio("Recorded method", ["self_review", "checker_feedback"], horizontal=True)
    chosen = pair["arms"][branch]
    record_dir = DEMO / "run" / pair["opaque_id"] / chosen["request_path"]
    record = json.loads((record_dir / "attempt.json").read_text())
    st.write("Recorded outcome: " + record["status"])
    if record.get("proposal"):
        st.write(record["proposal"]["explanation"])
    if record.get("error"):
        st.code(record["error"])
    if record.get("evaluation"):
        render_check(record["evaluation"], record_dir / "evaluation", pair["opaque_id"] + branch)
    st.download_button("Download complete case evidence", evidence(case_id, str(DEMO / "run" / pair["opaque_id"])),
                       file_name=pair["opaque_id"] + "-evidence.zip", key="case_evidence")
    st.caption("Original notices and per-source MIT / GPL-3.0-or-later licensing remain in the evidence. The root project license does not replace vendor licenses.")
    original = (DATA / case_id / "input.v").read_text()
    recorded_source = (record_dir / "candidate.v").read_text() if (record_dir / "candidate.v").exists() else original
    st.subheader("Edit this supported module")
    starting = st.radio("Starting source", ["Original input", "Recorded model candidate"], horizontal=True)
    editor_key = "known_editor_" + pair["opaque_id"] + branch + starting
    source = st.text_area("Editable known-case RTL", original if starting == "Original input" else recorded_source, height=320, key=editor_key)
    available, why = ready()
    if not available:
        st.info(why)
    check_key = "known_check_" + pair["opaque_id"]
    if st.button("Run sealed regression checks", disabled=not available, type="primary"):
        st.session_state.pop(check_key, None)
        try:
            with st.spinner("Compiling and checking the current source in an isolated worker…"):
                st.session_state[check_key] = fresh_check(case_id, source)
        except (ValueError, RuntimeError, OSError) as exc:
            st.error(str(exc))
    result = st.session_state.get(check_key)
    if result and result["rtl_sha256"] == sha256(source.encode()):
        render_check(result, result["directory"], "fresh_" + pair["opaque_id"])
        live = os.environ.get("RTLREFINE_ENABLE_LIVE_MODEL") == "1"
        eligible = live and available and not result["discovery_pass"]
        if st.button("Ask NVIDIA for one checked repair", disabled=not eligible):
            with st.spinner("One budgeted Nebius request, followed by sealed checks…"):
                model = live_repair(case_id, source, result)
            st.write("New model outcome: " + model["status"])
            if model.get("evaluation"):
                render_check(model["evaluation"], Path(model["directory"]) / "evaluation", "new_model")
            elif model.get("error"):
                st.error(model["error"])
        st.download_button("Download current-check evidence", evidence(case_id, result["directory"]), file_name="current-check-evidence.zip", key="current_evidence")
    elif result:
        st.info("Source changed. Run checks on the applied edits before using a prior result.")
    st.caption("Browsing, editing and sealed regression checks make no model request. A new repair request is optional, server-enabled and subject to the persistent budget cap.")


if __name__ == "__main__":
    main()
