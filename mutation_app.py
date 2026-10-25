"""Synthetic fault repair against public properties, without fixed RTL scoring."""
from __future__ import annotations

import difflib
import io
import json
import os
from pathlib import Path
import zipfile

import pandas as pd
import streamlit as st

from rtl_agent.common import ROOT, new_run_dir, sha256, write_json
from rtl_agent.model_client import ModelError
from rtl_agent.mutations.agent import MAX_TOKENS, MutationClient, messages, parse_proposal
from rtl_agent.mutations.contract import DATA, source_policy, specification
from rtl_agent.mutations.evaluator import evaluate, feedback, snapshot
from workspace_app import readiness
from workspace_service import execution_slot

DEMO = ROOT / "demo/mutation_challenge"


def evidence(directory):
    directory = Path(directory)
    buffer, manifest = io.BytesIO(), {}
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(directory.rglob("*")):
            if file.is_file() and (file.suffix in (".json", ".v", ".vh", ".csv", ".vcd", ".ys", ".log", ".py", ".patch", ".md") or file.name == "COPYING") and file.name != "manifest.json":
                name, content = str(file.relative_to(directory)), file.read_bytes()
                archive.writestr(name, content)
                manifest[name] = {"sha256": sha256(content), "bytes": len(content)}
        for parent in (directory, *list(directory.parents)[:3]):
            folder = parent / "checker_source"
            if not folder.is_dir():
                continue
            for file in sorted(folder.glob("*.py")):
                name, content = "checker_source/" + file.name, file.read_bytes()
                if name not in manifest:
                    archive.writestr(name, content)
                    manifest[name] = {"sha256": sha256(content), "bytes": len(content)}
            break
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
    return buffer.getvalue()


def fresh_check(source):
    directory = new_run_dir("property_workspace_review")
    snapshot(directory)
    with execution_slot():
        return evaluate(source, directory / "evaluation")


def request_repair(source, previous):
    source_policy(source)
    if previous["rtl_sha256"] != sha256(source.encode()) or previous["accepted"]:
        raise ValueError("Check the exact current failing source before requesting a repair")
    directory = new_run_dir("property_workspace_nvidia")
    snapshot(directory)
    client = MutationClient()
    client.verify_model()
    prompt = messages(source, previous={"decision": "keep", "rtl": source, "explanation": "Designer-submitted candidate"}, observations=feedback(previous))
    write_json(directory / "messages.json", prompt)
    record = {"status": "MODEL_RESPONSE_ERROR", "accepted": False, "directory": str(directory)}
    try:
        response = client.generate(prompt, max_tokens=MAX_TOKENS)
        write_json(directory / "response.json", response)
        proposal = parse_proposal(response, source)
        write_json(directory / "proposal.json", proposal)
        with execution_slot():
            result = evaluate(proposal["rtl"], directory / "evaluation")
        record.update({"status": result["status"], "accepted": result["accepted"], "proposal": proposal, "evaluation": result})
    except (ModelError, ValueError, RuntimeError, OSError, KeyError, IndexError, TypeError) as exc:
        record["error"] = client.redact(str(exc))
    record["cost"] = client.last_cost
    write_json(directory / "model_run.json", record)
    return record


def render_evaluation(result, directory, key):
    digest = sha256((directory / "candidate.v").read_bytes())
    if digest != result["rtl_sha256"]:
        raise ValueError("The displayed source no longer matches the evaluation")
    if result["accepted"]:
        st.success("VERIFIED AGAINST SPEC WITHIN BOUND")
    else:
        st.error("NOT ACCEPTED · " + result["status"])
    if result.get("error"):
        st.write(result["error"])
    a, b, c, d = st.columns(4)
    a.metric("Discovery simulations", f"{sum(s['passed'] for s in result['discovery_simulations'])}/3")
    b.metric("Unexposed audit simulations", f"{sum(s['passed'] for s in result['audit_simulations'])}/3")
    c.metric("Specification properties", f"{sum(p['status']=='BOUNDED_PROPERTY_PASS' for p in result['formal'])}/2")
    d.metric("Golden RTL used", "No")
    st.caption("Checked source SHA-256: " + digest)
    st.caption("Property review ID: " + directory.parent.name)
    st.caption(result["limitation"])
    simulations = result["discovery_simulations"] + result["audit_simulations"]
    if simulations:
        selected = next((s for s in simulations if not s["passed"]), simulations[0])
        if selected["first_violations"]:
            st.write("First contract violations")
            st.json(selected["first_violations"][:3])
        rows = selected["observations"]
        controls = {"Cycle": [r["cycle"] for r in rows]}
        for field in ("s_valid", "s_ready", "m_valid", "m_ready"):
            controls[field] = [int(r[field]) if r[field] in ("0", "1") else None for r in rows]
        st.line_chart(pd.DataFrame(controls).set_index("Cycle"), height=180)
        st.caption("Actual Icarus interface samples. Unknown handshake values are left undefined in the chart.")
    replay = [p for p in result["formal"] if p.get("replay")]
    if replay:
        st.table([{"Memory words": 1 << p["profile"]["addr_width"], "Bound": p["profile"]["steps"],
                   "Property result": p["status"], "Same-input Icarus replay": p["replay"]["status"]} for p in replay])
    with st.expander("Inspect assumptions and independent property results"):
        st.json(result["formal"])
    if result["accepted"]:
        st.download_button("Download spec-checked RTL", (directory / "candidate.v").read_bytes(), file_name="stream_buffer.v", key="rtl_" + key)
    st.download_button("Download property-check evidence", evidence(directory), file_name="RTLRefine-property-evidence.zip", key="evidence_" + key)


def main():
    st.set_page_config(page_title="RTLRefine · Synthetic property challenge", layout="wide")
    st.caption("RTLREFINE · SYNTHETIC FAULTS · NO FIXED RTL ORACLE")
    st.title("Repair the fault. Keep the contract.")
    st.write("Inspect deliberately injected queue faults and NVIDIA repairs checked against a public behavioral specification.")
    st.info("This is a constructed mutation experiment on one authored queue. It is not a newly discovered real-world bug or an external held-out benchmark.")
    summary_file = DEMO / "run/summary.json"
    summary = json.loads(summary_file.read_text()) if summary_file.is_file() else None
    if summary:
        a, b, c = st.columns(3)
        a.metric("Injected cases repaired by NVIDIA", f"{summary['accepted_repairs']}/{summary['injected_cases']}")
        b.metric("Normal controls kept unchanged", f"{summary['controls_kept_unchanged']}/{summary['normal_controls']}")
        c.metric("Frozen-run API requests", summary["unique_paid_calls"])
        st.caption(f"Frozen eight-case experiment: at most two requests per independent model context. Estimated API cost ${summary['estimated_api_cost_usd']:.4f}. No pristine source or mutation map is sent for a faulted case. Audit observations neither enter feedback nor control retries.")
    else:
        st.write("The frozen repair experiment is running. Completed results will be shown after the whole run is audited.")
    with st.expander("Read the public behavioral contract"):
        st.json(specification())
        st.caption("The formal monitor uses an abstract shift queue and a universally selected constant bit; the RTL candidate can use a different implementation. Simulations use Python deque. No fixed implementation is instantiated as a scoring oracle.")
    dataset = json.loads((DATA / "dataset.json").read_text())
    entry = st.selectbox("Sealed candidate", dataset["cases"], format_func=lambda row: row["case_id"])
    case_id = entry["case_id"]
    original = (DATA / entry["source"]).read_text()
    if sha256(original.encode()) != entry["source_sha256"]:
        raise ValueError("The sealed input source changed")
    if summary:
        row = next(r for r in summary["cases"] if r["case_id"] == case_id)
        if not row["injected_fault"] and row["last_decision"] == "repair":
            st.warning("Recorded experiment: this sealed input is a normal control. NVIDIA proposed an unnecessary repair; it is not counted as a repaired fault.")
        with st.expander("Reveal synthetic injection metadata · evaluation only"):
            st.json({"kind": row["kind"], "injected_fault": row["injected_fault"], "operators": row["operators"]})
            st.caption("These labels are joined for reporting after inference. They are not part of the repair-model context.")
    tabs = st.tabs(("Executed evidence", "Edit and check RTL"))
    with tabs[0]:
        before = DEMO / f"qualification/{case_id}/evaluation.json"
        if before.is_file():
            st.subheader("Input candidate · specification check")
            render_evaluation(json.loads(before.read_text()), before.parent, "input_" + case_id)
        case_file = DEMO / f"run/{case_id}/case.json"
        if case_file.is_file():
            run = json.loads(case_file.read_text())
            selected = next((a for a in run["attempts"] if a["accepted"]), run["attempts"][-1])
            st.subheader("NVIDIA result · " + selected["status"])
            st.caption("Recorded actual Nebius response; viewing this record does not call a model.")
            if selected.get("proposal"):
                st.write(selected["proposal"]["explanation"])
                patch = "".join(difflib.unified_diff(original.splitlines(True), selected["proposal"]["rtl"].splitlines(True), fromfile="submitted.v", tofile="nvidia.v"))
                st.code(patch or "No functional change requested", language="diff")
            if "evaluation" in selected:
                directory = case_file.parent / f"attempt_{selected['number']}/evaluation"
                render_evaluation(selected["evaluation"], directory, "model_" + case_id)
            else:
                st.error(selected.get("error", selected["status"]))
            with st.expander("All retained model attempts for this candidate"):
                st.json([{k: a.get(k) for k in ("number", "status", "accepted", "error", "cost")} for a in run["attempts"]])
    with tabs[1]:
        choice = st.radio("Starting RTL", ("Sealed input", "Recorded accepted repair"), horizontal=True)
        value = original
        if choice == "Recorded accepted repair" and summary:
            row = next(r for r in summary["cases"] if r["case_id"] == case_id)
            if row["accepted_source"]:
                value = (DEMO / "run" / row["accepted_source"]).read_text()
            else:
                st.warning("No accepted repair was recorded for this candidate; sealed input loaded.")
        source = st.text_area("Queue RTL source", value, height=300, max_chars=16000, key="property_source_" + case_id + choice)
        ready, detail = readiness()
        if not ready:
            st.warning("Isolated execution unavailable: " + detail)
        clicked = st.button("Run specification checks", disabled=not ready, type="primary")
        slot = st.empty()
        if clicked:
            st.session_state.pop("property_review", None)
            slot.info("Checking the submitted bytes; no new result is accepted yet.")
            with st.spinner("Independent simulation, public properties and counterexample replay…"):
                try:
                    st.session_state["property_review"] = fresh_check(source)
                except (ValueError, RuntimeError, OSError) as exc:
                    st.error(str(exc))
        checked = st.session_state.get("property_review")
        matches = checked and checked["rtl_sha256"] == sha256(source.encode())
        if checked:
            if not matches:
                st.warning("The current source differs from the checked file. Run the specification checks again.")
            with slot.container():
                render_evaluation(checked, Path(checked["directory"]), "edited")
        with st.expander("Request one NVIDIA repair against this specification"):
            live = os.environ.get("RTLREFINE_ENABLE_LIVE_MODEL") == "1"
            st.caption("One explicit paid request, bounded by the persistent budget ledger. Only this source, contract and discovery feedback are sent; the pristine implementation, mutation map and audit results are excluded.")
            if st.button("Ask NVIDIA for a spec-checked repair", disabled=not (live and ready and matches and not checked["accepted"])):
                with st.spinner("NVIDIA proposal followed by independent specification checks…"):
                    try:
                        st.session_state["property_model"] = request_repair(source, checked)
                    except Exception as exc:
                        st.error(str(exc))
        if "property_model" in st.session_state:
            model = st.session_state["property_model"]
            st.write("Live NVIDIA result: " + model["status"])
            if model.get("error"):
                st.error(model["error"])
            if model.get("evaluation"):
                render_evaluation(model["evaluation"], Path(model["directory"]) / "evaluation", "live")
            st.download_button("Download this property-repair run", evidence(model["directory"]), file_name="RTLRefine-property-repair.zip")


if __name__ == "__main__":
    main()
