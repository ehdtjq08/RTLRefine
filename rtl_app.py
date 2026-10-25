"""Focused hackathon application: supported sequential RTL debugging only."""
import streamlit as st


def home():
    from repair_studio_app import render_studio
    render_studio()
    with st.expander("Research archive and previous experiments"):
        archive()


def archive():
    st.caption("PRIOR RECORDED RTL EXPERIMENTS")
    st.page_link("evidence_ranking_app.py", label="Inspect evidence-based patch priorities and the new-module evaluation")
    st.page_link("repair_search_app.py", label="Inspect constrained search with NVIDIA candidate ranking")
    st.page_link("known_bugs_v2_app.py", label="Inspect the frozen comparison on nine known RTL bugs")
    st.page_link("uart_app.py", label="Inspect another author's UART flow-control bug")
    st.page_link("mutation_app.py", label="Repair injected faults against a specification")
    st.page_link("workspace_app.py", label="Open the editable RTL workspace", icon="🛠")
    st.page_link("case_gallery_app.py", label="Inspect three real historical RTL bugs")
    st.page_link("comparison_app.py", label="Inspect the controlled NVIDIA comparison")
    a, b, c = st.columns(3)
    a.metric("Historical RTL cases", "13")
    b.metric("Known-bug comparison cases", "9")
    c.metric("Physical FPGA needed", "No")
    st.write("Reset flushes, byte-valid masks and frame-FIFO backpressure each have different ways to look fixed while still failing. The workspace preserves the original, checks submitted RTL in isolated workers, and exports source, observed traces, proof scope and provenance.")
    st.write("The synthetic queue challenge checks edits against a public behavioral contract using Python deque and formal properties, without loading a corrected RTL implementation. Its constructed faults and healthy controls are labeled separately from the historical bugs.")
    st.write("The external UART case comes from ZipCPU, a different author and project. Its CTS gating and serial frames are checked from external ports without a corrected RTL oracle. Original failures, the model's first decision and all later outcomes remain visible.")
    st.write("A separate frozen comparison covers nine known historical research-artifact defects and two normal controls. It uses cycle-exact golden traces, shares the first NVIDIA proposal between arms, and keeps every failure and audit rejection.")
    st.info("Supported scope: three original historical stream cases, one historical UART, nine known-bug scenarios and one authored queue contract at listed parameters. Each workspace states whether it uses reference agreement, golden traces or independent specification properties. These checks do not establish unbounded correctness or arbitrary RTL support.")
    st.caption("NVIDIA Nemotron runs through Nebius Token Factory. Browsing recorded results and checking your own RTL make no model requests. Live model repair is an optional server setting with a persistent budget limit.")


page = st.navigation([
    st.Page(home, title="RTLRefine", default=True),
    st.Page("project_app.py", title="Your RTL project", url_path="project"),
    st.Page("evidence_ranking_app.py", title="Evidence ranking", url_path="ranking"),
    st.Page("workspace_app.py", title="Review your RTL", url_path="workspace"),
    st.Page("mutation_app.py", title="Synthetic property challenge", url_path="mutation"),
    st.Page("uart_app.py", title="External UART case", url_path="uart"),
    st.Page("known_bugs_v2_app.py", title="Known-bug comparison", url_path="benchmarks"),
    st.Page("repair_search_app.py", title="Constrained repair search", url_path="search"),
    st.Page("case_gallery_app.py", title="Real RTL cases", url_path="cases"),
    st.Page("comparison_app.py", title="NVIDIA comparison", url_path="comparison"),
])
page.run()
