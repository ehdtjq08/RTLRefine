"""Designer-facing review of editable RTL for three explicitly supported cases."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from rtl_agent.common import ROOT, sha256
from rtl_agent.sequential.case_review import CASES, evidence_zip, get_case, original_source
from rtl_agent.sequential.runner import SequentialRunner
from rtl_agent.tool_paths import find_tool
from workspace_service import check_change, recorded_candidate, request_repair


@st.cache_data(ttl=60)
def readiness():
    names = ("yosys", "iverilog", "vvp", "bwrap", "prlimit")
    if not all(find_tool(name) for name in names):
        return False, "This server does not have all required RTL tools."
    return SequentialRunner(timeout=60).probe(ROOT / ".state/workspace_probe")


def render_result(result, key):
    st.subheader("Independent review result")
    if result["accepted"]:
        st.success("VERIFIED WITHIN BOUND · Every directed regression and bounded comparison passed.")
    else:
        st.error("NOT ACCEPTED · " + result["status"])
    if result.get("error"):
        st.write(result["error"])
    simulations, proofs = result["simulations"], result["bounded_comparisons"]
    a, b, c = st.columns(3)
    a.metric("Simulation regressions", f"{sum(s['passed'] for s in simulations)}/{6 if result['case']=='axis_keep' else 3}")
    b.metric("Bounded checks passed", f"{sum(p['status']=='BOUNDED_PASS' for p in proofs)}/{4 if result['case']=='axis_keep' else 1}")
    c.metric("Model calls for this review", "0")
    st.caption(result["limitation"])
    st.caption("Reviewed source SHA-256: " + result["rtl_sha256"])
    st.caption("Review ID: " + Path(result["directory"]).parent.name)
    if simulations:
        if result["case"] == "fifo_reset":
            st.table([{"Clock half periods / prefill": str(s["variant"]), "Stale transfers": len(s["stale_transfers"]),
                       "Fresh transfers": len(s["fresh_actual"]), "Result": "PASS" if s["passed"] else "FAIL"} for s in simulations])
            selected = simulations[0]
        else:
            st.table([{"Variant": str(s["variant"]), "Expected bytes": s["expected_bytes"], "Received bytes": s["actual_bytes"],
                       "Expected frames": len(s["expected_frames"]), "Received frames": len(s["actual_frames"]),
                       "Result": "PASS" if s["passed"] else "FAIL"} for s in simulations])
            selected = next((s for s in simulations if not s["passed"]), simulations[0])
        rows = selected["observations"]
        time = [r["time_ps"] / 1000 for r in rows]
        signals = {"Time (ns)": time, "Output valid": [r["valid"] for r in rows], "Output ready": [r["ready"] for r in rows]}
        if result["case"] != "fifo_reset":
            signals["Input ready"] = [r["input_ready"] for r in rows]
        st.line_chart(pd.DataFrame(signals).set_index("Time (ns)"), height=180)
        st.caption("Actual Icarus observations for the first failing regression, or the first passing regression if all pass.")
    directory = Path(result["directory"])
    with st.expander("Inspect the exact source change"):
        st.code((directory / "candidate.patch").read_text() or "No source change", language="diff")
    with st.expander("Proof scope and execution records"):
        st.json(proofs)
        st.caption("No bounded check is reported as a pass after an error or timeout. Payload comparisons are qualified by reference validity; byte masks also qualify AXI adapter payload comparisons.")
    if result["accepted"]:
        st.download_button("Download verified RTL", (directory / "candidate.v").read_bytes(), file_name=get_case(result["case"])["file"], key="source_" + key)
    st.download_button("Download this review's evidence", evidence_zip(directory),
                       file_name="RTLRefine-" + result["case"] + "-review.zip", mime="application/zip", key="evidence_" + key)


def main():
    st.set_page_config(page_title="RTLRefine · Review your RTL", layout="wide")
    st.caption("RTLREFINE · EDIT → CHECK → INSPECT → EXPORT")
    st.title("Check your RTL change.")
    st.write("Edit a supported module, inspect real failure observations, and export a change only after the independent checks pass.")
    case_id = st.selectbox("Supported RTL contract", list(CASES), format_func=lambda value: CASES[value]["title"])
    case = get_case(case_id)
    st.info(case["contract"])
    st.caption("Three pinned historical cases are supported. Keep the template license, parameters, ports and configuration checks unchanged. Arbitrary RTL projects and unbounded correctness are outside this workflow.")
    starter = st.radio("Starting source", ("Historical original", "Recorded NVIDIA candidate", "Maintainer fix · evaluation control", "My RTL"), horizontal=True)
    if starter == "Recorded NVIDIA candidate":
        source, origin = recorded_candidate(case_id)
    elif starter == "Maintainer fix · evaluation control":
        source, origin = (case["assets"] / case["fixed"]).read_text(), "Historical maintainer fix · independent positive control, not a model-generated repair"
    else:
        source, origin = original_source(case_id), "Pinned historical original · edit this template or upload your module"
    st.caption(origin)
    uploaded = st.file_uploader("Optional Verilog upload", type=("v", "sv"), key="upload_" + case_id)
    if uploaded is not None:
        content = uploaded.getvalue()
        if len(content) > 24000:
            st.error("The supported module limit is 24 KB.")
            return
        try:
            source = content.decode("utf-8")
        except UnicodeDecodeError:
            st.error("Use a UTF-8 Verilog file.")
            return
        st.caption("Uploaded source: " + uploaded.name)
    st.caption("Source selection: " + case["title"] + " · " + starter + " · " + (uploaded.name if uploaded else "template"))
    token = sha256(uploaded.getvalue())[:12] if uploaded else "template"
    current = st.text_area("RTL source", source, height=340, max_chars=24000, key=f"source_{case_id}_{starter}_{token}")
    st.download_button("Download original template", original_source(case_id), file_name=case["file"])
    ready, detail = readiness()
    if not ready:
        st.warning("RTL execution is unavailable on this server: " + detail)
    clicked = st.button("Run independent checks", type="primary", disabled=not ready)
    result_slot = st.empty()
    if clicked:
        st.session_state.pop("rtl_workspace_review", None)
        result_slot.info("Checking the current source. No new result is accepted yet.")
        with st.spinner("Running isolated simulation and bounded comparisons…"):
            try:
                st.session_state["rtl_workspace_review"] = check_change(case_id, current)
            except (RuntimeError, ValueError, OSError) as exc:
                st.error(str(exc))
    result = st.session_state.get("rtl_workspace_review")
    matches = result is not None and result["case"] == case_id and result["rtl_sha256"] == sha256(current.encode())
    if result is not None:
        if not matches:
            st.warning("The source changed. The result below belongs to the previous submitted bytes; run the checks again for this edit.")
        with result_slot.container():
            render_result(result, "designer")
    with st.expander("Ask NVIDIA to repair the failing change"):
        live = os.environ.get("RTLREFINE_ENABLE_LIVE_MODEL") == "1"
        st.caption("Optional paid action: one Nemotron Ultra request on Nebius, capped at 16,384 output tokens and guarded by the persistent budget ledger. The model receives the supported original, submitted candidate and checker observations; never the maintainer reference source.")
        if not live:
            st.write("Live model requests are disabled for this server. Editable RTL verification and recorded executions remain available.")
        allowed = live and ready and matches and not result["accepted"]
        if st.button("Ask NVIDIA to repair this failing change", disabled=not allowed):
            with st.spinner("NVIDIA is proposing a complete candidate; independent checks follow…"):
                try:
                    st.session_state["rtl_workspace_model"] = request_repair(case_id, current, result)
                except Exception as exc:
                    st.error(str(exc))
    if "rtl_workspace_model" in st.session_state:
        model_run = st.session_state["rtl_workspace_model"]
        st.write("NVIDIA result: " + model_run["status"])
        if model_run.get("error"):
            st.error(model_run["error"])
        if model_run.get("proposal"):
            st.write(model_run["proposal"]["explanation"])
        if model_run.get("review"):
            render_result(model_run["review"], "model")
        st.download_button("Download this NVIDIA run", evidence_zip(model_run["directory"]), file_name="RTLRefine-NVIDIA-run.zip", key="model_evidence")


if __name__ == "__main__":
    main()
