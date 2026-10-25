"""Three historical failures with independent positive controls and scope."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from rtl_agent.common import ROOT, sha256
from rtl_agent.sequential.case_review import evidence_zip

DATA = ROOT / "demo/sequential_cases"


def load_record(relative):
    file = DATA / relative
    record = json.loads(file.read_text())
    directory = file.parent
    if sha256((directory / "candidate.v").read_bytes()) != record["rtl_sha256"]:
        raise ValueError("Recorded source changed after execution")
    record["directory"] = str(directory)
    return record


def main():
    st.set_page_config(page_title="RTLRefine · Real RTL cases", layout="wide")
    st.caption("RTLREFINE · PINNED SOURCE → OBSERVED FAILURE → INDEPENDENT CONTROL")
    st.title("Three real RTL failures.")
    index_path = DATA / "index.json"
    if not index_path.is_file():
        st.info("The fresh independent case controls are running.")
        return
    cases = json.loads(index_path.read_text())
    selected = st.selectbox("Historical case", range(len(cases)), format_func=lambda i: cases[i]["title"])
    case = cases[selected]
    st.info(case["contract"])
    source = case["source"]
    st.markdown(f"[Original repository]({source['repository']}) · [Actual maintainer fix]({source['fix']}) · MIT notices retained")
    st.caption("These are known public historical bugs, potentially present in model training. The maintainer changes are independent evaluation controls, not NVIDIA-generated fixes.")
    original, fixed = load_record(case["original_record"]), load_record(case["maintainer_record"])
    failed = next(s for s in original["simulations"] if not s["passed"])
    repaired = next(s for s in fixed["simulations"] if s["variant"] == failed["variant"])
    columns = st.columns(3)
    if case["case"] == "fifo_reset":
        columns[0].metric("Stale transfers after reset", f"{len(failed['stale_transfers'])} → {len(repaired['stale_transfers'])}")
        st.write("An old 0xA5 packet appears after reset. The independent regression also requires new 0x61 and 0x92 traffic to pass in order.")
    else:
        columns[0].metric("Valid bytes preserved", f"{failed['actual_bytes']} → {repaired['actual_bytes']}")
        left, right = st.columns(2)
        for column, label, simulation in ((left, "Historical original", failed), (right, "Maintainer positive control", repaired)):
            with column:
                st.markdown("**" + label + "**")
                st.table([{"Frame": i + 1, "Bytes": " ".join(f"{b:02X}" for b in frame["bytes"]), "ID": frame["id"], "DEST": frame["dest"]}
                          for i, frame in enumerate(simulation["actual_frames"])])
    columns[1].metric("Maintainer control regressions", f"{sum(s['passed'] for s in fixed['simulations'])}/{len(fixed['simulations'])}")
    columns[2].metric("Bounded comparison depth", str(case["proof_steps"]) + " steps")
    st.caption(f"Original status: {original['status']}. Maintainer control: {fixed['status']}. Directed regression shown: {failed['variant']}.")
    st.caption(fixed["limitation"])
    with st.expander("Provenance, parameters and proof records"):
        st.json(source)
        st.json({"original": original["bounded_comparisons"], "maintainer": fixed["bounded_comparisons"]})
    st.download_button("Download original failure evidence", evidence_zip(Path(original["directory"])),
                       file_name=case["case"] + "-original.zip", key="original")
    st.download_button("Download maintainer control evidence", evidence_zip(Path(fixed["directory"])),
                       file_name=case["case"] + "-maintainer-control.zip", key="fixed")
    st.page_link("workspace_app.py", label="Edit a module and run fresh checks")


if __name__ == "__main__":
    main()
