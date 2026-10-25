"""External historical UART repair, scored against the protocol, not fixed RTL."""
from __future__ import annotations

import difflib
import io
import json
from pathlib import Path
import zipfile

import pandas as pd
import streamlit as st

from rtl_agent.common import ROOT, new_run_dir, sha256
from rtl_agent.uart_external.contract import DATA, specification
from rtl_agent.uart_external.evaluator import evaluate, snapshot
from workspace_app import readiness
from workspace_service import execution_slot

DEMO = ROOT / "demo/external_uart"


def evidence(directory):
    directory = Path(directory)
    buffer, files = io.BytesIO(), {}
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix != ".vvp":
            files[str(path.relative_to(directory))] = path.read_bytes()
    for parent in (directory, *list(directory.parents)[:3]):
        if (parent / "checker_source").is_dir():
            for file in sorted((parent / "checker_source").glob("*.py")):
                files["checker_source/" + file.name] = file.read_bytes()
            break
    for file in sorted(DATA.iterdir()):
        if file.is_file():
            files["public_contract/" + file.name] = file.read_bytes()
    if (DEMO / "MODIFICATIONS.md").is_file():
        files["MODIFICATIONS.md"] = (DEMO / "MODIFICATIONS.md").read_bytes()
    manifest = {name: {"sha256": sha256(content), "bytes": len(content)} for name, content in files.items()}
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
    return buffer.getvalue()


def fresh_check(source):
    directory = new_run_dir("external_uart_workspace")
    snapshot(directory)
    with execution_slot():
        return evaluate(source, directory / "evaluation")


def render_result(result, directory, key):
    digest = sha256((directory / "candidate.v").read_bytes())
    if digest != result["rtl_sha256"]:
        raise ValueError("Source changed after checking")
    if result["accepted"]:
        st.success("VERIFIED AGAINST SPEC WITHIN BOUND")
    else:
        st.error("NOT ACCEPTED · " + result["status"])
    if result.get("error"):
        st.write(result["error"])
    a, b, c, d = st.columns(4)
    a.metric("Discovery serial / flow checks", f"{sum(s['passed'] for s in result['discovery_simulations'])}/6")
    b.metric("Unexposed audit checks", f"{sum(s['passed'] for s in result['audit_simulations'])}/6")
    c.metric("Bounded CTS properties", f"{sum(p['status']=='BOUNDED_PROPERTY_PASS' for p in result['formal'])}/2")
    d.metric("Golden RTL used for scoring", "No")
    st.caption("Checked RTL SHA-256: " + digest)
    st.caption(result["limitation"])
    simulations = result["discovery_simulations"] + result["audit_simulations"]
    if simulations:
        selected = next((s for s in simulations if not s["passed"]), simulations[0])
        if selected.get("first_violations"):
            st.write("Actual external-port contract violations")
            st.json(selected["first_violations"][:4])
        with st.expander("Serial frames and all tested configurations"):
            st.table([{"Baud clocks": s["profile"]["baud_cycles"], "Data bits": s["profile"]["data_bits"],
                       "Parity": s["profile"]["parity"], "Stops": s["profile"]["stop_bits"],
                       "Flow control": s["profile"]["flow_control"], "Passed": s["passed"],
                       "Complete frames": s.get("coverage", {}).get("complete_serial_frames", 0)} for s in simulations])
            st.json(selected.get("decoded_frames", [])[:8])
    proofs = result["formal"]
    if proofs:
        st.table([{"Baud clocks": p["profile"]["baud_cycles"], "Bound": p["profile"]["steps"],
                   "Property": p["status"], "Same-input Icarus replay": p.get("replay", {}).get("status", "No counterexample")} for p in proofs])
    with st.expander("Property assumptions and scope"):
        st.json(proofs)
    if result["accepted"]:
        st.download_button("Download checked UART RTL", (directory / "candidate.v").read_bytes(), file_name="txuart.v", key="rtl_" + key)
    st.download_button("Download UART evidence", evidence(directory), file_name="RTLRefine-UART-evidence.zip", key="evidence_" + key)
    st.caption("Vendor and derived txuart.v: GPL-3.0-or-later, copyright Gisselquist Technology. License and corresponding source are included in evidence.")


def main():
    st.set_page_config(page_title="RTLRefine · External UART", layout="wide")
    st.caption("RTLREFINE · ANOTHER AUTHOR'S REAL RTL · SPECIFICATION CHECKS")
    st.title("The receiver said stop. The UART sent anyway.")
    st.write("Reproduce a historical ZipCPU UART flow-control defect, inspect the actual NVIDIA patch, and check serial output independently.")
    st.info("This is one selected historical external bug, not an injected fault or a held-out repair benchmark. The maintainer fix qualifies the checker before inference; it is never a runtime scoring oracle or model input.")
    summary_path = DEMO / "run/summary.json"
    if not summary_path.is_file():
        st.write("The frozen external repair experiment has not been exported yet.")
        return
    summary = json.loads(summary_path.read_text())
    attempt = summary["attempts"][-1]
    original = (DEMO / "run/input.v").read_text()
    source = (DEMO / "run" / summary["accepted_source"]).read_text() if summary["accepted_source"] else original
    a, b, c = st.columns(3)
    a.metric("External historical case accepted", "1/1" if summary["accepted"] else "0/1")
    b.metric("Actual NVIDIA requests", summary["unique_paid_calls"])
    c.metric("Estimated model cost", f"${summary['estimated_api_cost_usd']:.4f}")
    st.caption("Recorded Nebius Token Factory inference. Fresh specification checks below make zero model requests. This result does not establish general accuracy or improvement over self-review.")
    if summary.get("posthoc_boundary_policy_fix"):
        st.caption("The fourth model candidate passed after correcting an indentation-only boundary parser bug. All four original request outcomes remain below; simulation and property checkers were unchanged.")
    with st.expander("Origin, public contract and excluded modes"):
        st.markdown("Original project: [ZipCPU/wbuart32](https://github.com/ZipCPU/wbuart32). Historical fix: [07e4c47](https://github.com/ZipCPU/wbuart32/commit/07e4c47166f0407c276bee571900ed2f9df06bad).")
        st.json(specification())
        st.write("Before inference, a divisor-two progress failure and computed-parity disagreement also appeared in the maintainer control. Those calibration failures are preserved; the CTS experiment excludes those modes.")
    view = st.radio("UART view", ["Executed external evidence", "Edit and check UART"], horizontal=True)
    if view == "Executed external evidence":
        st.subheader("Original: a legal writer trusts a false ready indication")
        baseline_dir = DEMO / "qualification/buggy"
        baseline = json.loads((baseline_dir / "evaluation.json").read_text())
        observation_file = baseline_dir / "discovery_simulations_0_1/observations.json"
        observations = json.loads(observation_file.read_text())
        failure_cycle = next(r["cycle"] for r in observations if r["phase"] == 3 and r["busy_after"] == 0)
        window = [r for r in observations if failure_cycle - 4 <= r["cycle"] <= failure_cycle + 8]
        st.dataframe(pd.DataFrame(window)[["cycle", "cts_n", "break", "write", "data", "busy_before", "busy_after", "tx_after"]], hide_index=True, width="stretch")
        render_result(baseline, baseline_dir, "original")
        st.subheader("Actual NVIDIA proposal")
        st.code("".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True), fromfile="original/txuart.v", tofile="nvidia/txuart.v")), language="diff")
        for record in summary["attempts"]:
            st.write(f"Request {record['number']}: {record['status']}")
            st.write(record.get("proposal", {}).get("explanation", record.get("error", "")))
        if "evaluation" in attempt:
            directory = DEMO / "run" / f"attempt_{attempt['number']}/evaluation"
            render_result(attempt["evaluation"], directory, "nvidia")
        if summary.get("final_evaluation"):
            st.subheader("Byte-identical fourth proposal: boundary-corrected recheck")
            st.write("Only the controller's source-boundary parser changed to accept the first declaration without a leading tab. Original and maintainer controls were requalified; the exact model source was then rechecked with no further API request.")
            render_result(summary["final_evaluation"], DEMO / "run" / summary["final_evaluation_location"], "boundary_recheck")
    else:
        choice = st.radio("UART starting source", ["Original external source", "Recorded NVIDIA candidate"], horizontal=True)
        chosen = original if choice.startswith("Original") else source
        key = "uart_editor_" + choice
        text = st.text_area("Editable UART RTL", chosen, height=360, key=key)
        ready, why = readiness()
        if not ready:
            st.warning(why)
        if st.button("Run UART specification checks", disabled=not ready, type="primary"):
            st.session_state.pop("uart_fresh_result", None)
            try:
                with st.spinner("Checking serial frames, CTS gating and bounded properties in isolated workers…"):
                    st.session_state["uart_fresh_result"] = fresh_check(text)
            except (ValueError, RuntimeError, OSError) as exc:
                st.error(str(exc))
        result = st.session_state.get("uart_fresh_result")
        if result and result["rtl_sha256"] == sha256(text.encode()):
            render_result(result, Path(result["directory"]), "fresh")
        elif result:
            st.info("Source changed. Check the current source before using a previous result.")


if __name__ == "__main__":
    main()
