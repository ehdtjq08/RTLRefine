"""Web-only view of a historical RTL reset failure and checked NVIDIA edits."""
from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from ..common import ROOT, new_run_dir, sha256, write_json
from ..model_client import load_local_env
from ..tool_paths import find_tool
from .repair import run
from .reset_case import ASSETS, bounded_compare, simulate
from .runner import SequentialRunner

DEMO = ROOT / "demo/fifo_reset"
ULTRA = "nvidia/Nemotron-3-Ultra-550b-a55b"


def load_case():
    path = DEMO / "current.json"
    return json.loads(path.read_text()) if path.is_file() else None


def verified_attempt(record, directory):
    path = record.get("accepted_rtl")
    if not path:
        return None, None
    source = (directory / path).read_text()
    expected = sha256(source.encode())
    attempt = next((a for a in record["attempts"] if a.get("rtl_sha256") == expected and
                    a.get("bounded", {}).get("status") == "BOUNDED_PASS" and
                    len(a.get("simulations", [])) == 3 and
                    all(s["passed"] for s in a.get("simulations", []))), None)
    if attempt is None:
        raise ValueError("Recorded RTL bytes do not match a checked repair")
    return source, attempt


def recheck(source):
    directory = new_run_dir("fifo_web_recheck")
    runner = SequentialRunner(timeout=60)
    ready, detail = runner.probe(directory / "isolation")
    if not ready:
        raise RuntimeError(detail)
    simulations = [simulate(source, directory / f"sim_{i}", runner, variant) for i, variant in enumerate(
        ((5, 7, 1), (7, 5, 3), (5, 11, 2)))]
    proof = bounded_compare(source, directory / "bounded", runner, 16)
    result = {"status": "VERIFIED_WITHIN_BOUND" if all(s["passed"] for s in simulations) and proof["status"] == "BOUNDED_PASS" else "UNVERIFIED",
              "new_api_requests": 0, "simulations": simulations, "bounded": proof,
              "rtl_sha256": sha256(source.encode())}
    write_json(directory / "recheck.json", result)
    return result


def _packets(simulation, phase):
    packets = []
    for row in simulation["observations"]:
        if row["phase"] == phase and row["valid"] and row["ready"]:
            bits = row["data_bits"]
            value = f"0x{int(bits, 2):02X}" if set(bits) <= {"0", "1"} else bits
            packets.append({"Time (ns)": row["time_ps"] / 1000, "Data": value,
                            "TLAST": row["last_bits"], "TUSER": row["user_bits"]})
    return packets


def render_record(record, directory, key):
    st.caption(record["model"] + " · Nebius Token Factory")
    source, attempt = verified_attempt(record, directory)
    if source is None:
        st.warning("No repair from this run passed the complete acceptance gate.")
        st.json([{k: a[k] for k in ("attempt", "status", "error", "cost") if k in a} for a in record["attempts"]])
        return
    baseline = record["baseline"]
    repaired = attempt["simulations"][0]
    columns = st.columns(3)
    columns[0].metric("Stale transfers after reset", f"{len(baseline['stale_transfers'])} → {len(repaired['stale_transfers'])}")
    columns[1].metric("Clock / occupancy regressions", f"{sum(s['passed'] for s in attempt['simulations'])}/3")
    columns[2].metric("Bounded comparison", f"{attempt['bounded']['steps']} steps")
    st.caption("Four-word, 8-bit FIFO instance. The comparison covers 12 interface bits, with payload/sidebands checked when valid. It is not unbounded equivalence or CDC sign-off.")
    st.subheader("The old packet crosses the reset boundary.")
    left, right = st.columns(2)
    for column, label, simulation in ((left, "Original RTL", baseline), (right, "NVIDIA-proposed RTL", repaired)):
        with column:
            st.markdown("**" + label + "**")
            packets = _packets(simulation, 3)
            if packets:
                st.table(packets)
            else:
                st.write("No pre-reset packet transferred.")
            selected = [row for row in simulation["observations"] if row["phase"] in (2, 3)]
            data = pd.DataFrame({"Time (ns)": [r["time_ps"] / 1000 for r in selected],
                                 "Reset": [r["output_reset"] for r in selected],
                                 "Valid": [r["valid"] for r in selected], "Ready": [r["ready"] for r in selected]})
            st.line_chart(data.set_index("Time (ns)"), height=210)
    st.caption("These waveforms are captured Icarus observations. During the post-reset observation window, the testbench issues no new input transfers.")
    st.subheader("New traffic still works.")
    st.table(_packets(repaired, 4))
    st.caption("The independent regression expects 0x61 then 0x92, including TLAST/TUSER. Suppressing output-valid permanently cannot pass.")
    with st.expander("Inspect the NVIDIA edits and explanation", expanded=True):
        st.write(attempt.get("proposal", {}).get("explanation", ""))
        patch = record.get("patch_path")
        if patch and (directory / patch).is_file():
            st.code((directory / patch).read_text(), language="diff")
        st.caption("The fixed upstream source is evaluation-only and is excluded from model prompts. This is a known historical bug, not a new discovery.")
    st.download_button("Download checked RTL", source, file_name="axis_async_fifo.v", key="rtl_" + key)
    with st.expander("Proof scope, failure history, and provenance"):
        st.json(attempt["bounded"])
        if record.get("development_note"):
            st.write(record["development_note"])
        for a in record["attempts"]:
            st.write(f"Attempt {a.get('attempt', '?')}: {a['status']}")


def render_workspace():
    st.set_page_config(page_title="RTLRefine · FIFO reset repair", layout="wide")
    st.caption("RTLREFINE · HISTORICAL RTL BUG")
    st.title("Reset should mean empty.")
    st.write("Reproduce an asynchronous FIFO reset failure, inspect NVIDIA's RTL edits, and check that old data stays discarded.")
    st.markdown("Source: [verilog-axis issue #2](https://github.com/alexforencich/verilog-axis/issues/2). Original and fixed commits are pinned; upstream MIT notices are retained.")
    cached = load_case()
    if cached is None:
        st.info("The first checked RTL case is being packaged.")
        return
    st.caption("Browsing these executed records makes no API calls. All simulation and proof tools run on the server; no physical board is required.")
    render_record(cached, DEMO, "recorded")
    source, _ = verified_attempt(cached, DEMO)
    ready = all(find_tool(name) for name in ("yosys", "iverilog", "vvp", "bwrap", "prlimit"))
    if st.button("Recheck the saved RTL with fresh tools", disabled=not ready):
        with st.spinner("Running isolated simulation and bounded comparison…"):
            try:
                st.session_state["fifo_recheck"] = recheck(source)
            except Exception as exc:
                st.error(str(exc))
    if "fifo_recheck" in st.session_state:
        st.write("Fresh recheck: " + st.session_state["fifo_recheck"]["status"] + " · no model calls")
    with st.expander("Ask NVIDIA for a new repair"):
        load_local_env()
        choice = st.selectbox("NVIDIA model", ("Configured NVIDIA model", "Nemotron 3 Ultra"), index=1)
        use_ultra = choice == "Nemotron 3 Ultra"
        st.caption("Configured model: up to two 8,192-token attempts. Ultra: one reasoning attempt with a 16,384-token cap. The persistent budget ledger applies; all failures remain recorded.")
        if st.button("Generate and validate a repair", disabled=not ready or not os.environ.get("NEBIUS_API_KEY")):
            with st.spinner("NVIDIA is proposing local edits; independent tools will check them…"):
                try:
                    st.session_state["fifo_live"] = run(max_requests=1 if use_ultra else 2,
                        thinking=use_ultra, model_id=ULTRA if use_ultra else None,
                        max_tokens=16384 if use_ultra else 8192)
                except Exception as exc:
                    st.error(str(exc))
        if "fifo_live" in st.session_state:
            current = st.session_state["fifo_live"]
            current["patch_path"] = "accepted.patch"
            render_record(current, Path(current["directory"]), "live")
    if (DEMO / "manifest.json").is_file():
        buffer = io.BytesIO()
        exported = {}
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in DEMO.rglob("*"):
                if file.is_file() and file != DEMO / "manifest.json" and file.suffix in (".json", ".v", ".vcd", ".csv", ".ys", ".log", ".patch", ".md", ".py"):
                    name = str(file.relative_to(DEMO))
                    content = file.read_bytes()
                    archive.writestr(name, content)
                    exported[name] = {"sha256": sha256(content), "bytes": len(content)}
            license_bytes = (ASSETS / "COPYING").read_bytes()
            archive.writestr("UPSTREAM_COPYING", license_bytes)
            exported["UPSTREAM_COPYING"] = {"sha256": sha256(license_bytes), "bytes": len(license_bytes)}
            archive.writestr("manifest.json", json.dumps(exported, indent=2))
        st.download_button("Download RTL verification evidence", buffer.getvalue(),
                           file_name="RTLRefine-FIFO-reset-evidence.zip", mime="application/zip")
