"""Display the complete frozen paired fork without pooling development pilots."""
import json

import streamlit as st

from rtl_agent.common import ROOT


def main():
    st.set_page_config(page_title="RTLRefine · NVIDIA comparison", layout="wide")
    st.caption("RTLREFINE · SAME FIRST PROPOSAL · SAME MODEL · SAME CALL CAP")
    st.title("Measure what the feedback changes.")
    folder = ROOT / "demo/sequential_comparison"
    if not (folder / "summary.json").is_file():
        st.info("The fixed three-case paired experiment is running. Results will be shown after the complete run is audited.")
        return
    result = json.loads((folder / "summary.json").read_text())
    protocol = json.loads((folder / "protocol.json").read_text())
    st.write("Both branches share the same first NVIDIA proposal. If it fails, one branch receives an independent self-review request and the other receives checker observations. Each branch has at most two logical model calls.")
    a, b, c = st.columns(3)
    for column, name, title in ((a, "self_review", "Self-review accepted"), (b, "checker_feedback", "Checker feedback accepted")):
        total = result["totals"][name]
        column.metric(title, f"{total['accepted']}/{total['pairs']}")
    c.metric("Unique paid requests", result["actual_unique_paid_calls"])
    st.table([{"Case": pair["case"], "Trial": pair["trial"], "Shared first result": pair["shared_initial_status"],
               "Self-review": pair["arms"]["self_review"]["status"], "Checker feedback": pair["arms"]["checker_feedback"]["status"]}
              for pair in result["pairs"] if set(pair["arms"]) == {"self_review", "checker_feedback"}])
    st.write(f"Estimated cost of unique requests: ${result['estimated_api_cost_usd']:.4f}. Shared requests are counted once; per-branch attributed costs cannot be added together.")
    st.warning("This small development cohort does not establish general superiority. The cases are public historical bugs, the two earlier cases informed development, and training-data familiarity is unknown. Failures and incomplete proofs remain failures.")
    st.caption("Feedback includes independently observed simulation failures and symbolic bounded-comparison input witnesses. Those symbolic witnesses are not independently replayed; the simulation traces are separate directed witnesses.")
    with st.expander("Frozen protocol and complete result records"):
        st.json(protocol)
        st.json(result)
    st.download_button("Download comparison summary", json.dumps(result, indent=2), file_name="RTLRefine-paired-summary.json")


if __name__ == "__main__":
    main()
