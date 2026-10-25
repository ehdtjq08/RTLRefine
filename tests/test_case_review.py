import io
import json
import zipfile

import pytest

from rtl_agent.sequential.case_agent import messages
from rtl_agent.sequential.case_review import CASES, evaluate, evidence_zip, feedback, original_source, source_policy, symbolic_inputs
from rtl_agent.sequential.runner import SequentialRunner
from rtl_agent.tool_paths import find_tool


@pytest.fixture
def runner(tmp_path):
    if not all(find_tool(name) for name in ("yosys", "iverilog", "vvp", "bwrap", "prlimit")):
        pytest.skip("Optional EDA tools unavailable")
    instance = SequentialRunner(timeout=60)
    ok, reason = instance.probe(tmp_path / "probe")
    if not ok:
        pytest.skip(reason)
    return instance


def test_three_real_sources_and_fixes_preserve_the_review_boundary():
    for name, case in CASES.items():
        for file in (case["file"], case["fixed"]):
            source_policy(name, (case["assets"] / file).read_text())
        original = original_source(name)
        for injected in ('initial $system("bad");', "wire y = miter.foo;", "module extra;endmodule", "`include bad.v"):
            with pytest.raises(ValueError):
                source_policy(name, original.replace("endmodule", injected + "\nendmodule", 1))
        with pytest.raises(ValueError):
            source_policy(name, original.replace("parameter", "parameter hacked = 1, parameter", 1))


def test_frame_failure_is_burst_specific_and_maintainer_control_passes(tmp_path, runner):
    case = CASES["frame_fifo"]
    baseline = evaluate("frame_fifo", original_source("frame_fifo"), tmp_path / "original", runner=runner, formal_on_failure=True)
    assert baseline["status"] == "SIMULATION_FAILED" and not baseline["accepted"]
    assert [s["passed"] for s in baseline["simulations"]] == [True, True, False]
    assert baseline["simulations"][2]["actual_bytes"] == 16
    assert baseline["bounded_comparisons"][0]["status"] == "COUNTEREXAMPLE"
    fixed = evaluate("frame_fifo", (case["assets"] / case["fixed"]).read_text(), tmp_path / "fixed", runner=runner)
    assert fixed["accepted"] and fixed["status"] == "VERIFIED_WITHIN_BOUND"
    assert fixed["bounded_comparisons"][0]["steps"] == 12
    assert all(s["actual_bytes"] == 24 for s in fixed["simulations"])
    with zipfile.ZipFile(io.BytesIO(evidence_zip(tmp_path / "fixed"))) as archive:
        assert archive.read("COPYING") == (case["assets"] / "COPYING").read_bytes()
        assert "simulation.vvp" not in " ".join(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        assert len(archive.namelist()) == len(manifest) + 1
    observation = feedback(baseline, tmp_path / "original")
    signals = observation["bounded_results"][0]["symbolic_input_trace"]["signal"]
    assert signals and all("." not in s["name"] for s in signals)
    assert not any("golden" in s["name"] for s in signals)
    prompt = json.dumps(messages("frame_fifo", baseline))
    assert "wire full_wr" not in prompt and "reference_frame_fifo" not in prompt


def test_unsafe_source_never_reaches_a_worker(tmp_path):
    class NeverRun:
        def probe(self, path):
            pytest.fail("Policy-rejected input reached a worker")
    bad = original_source("fifo_reset").replace("endmodule", 'initial $system("bad");\nendmodule')
    result = evaluate("fifo_reset", bad, tmp_path / "unsafe", runner=NeverRun())
    assert result["status"] == "POLICY_REJECTED" and not result["accepted"]


def test_yosys_internal_escape_error_does_not_leak_reference_state_or_drop_inputs(tmp_path):
    file = tmp_path / "trace.json"
    file.write_text('{"signal":[\n{"name":"clk","wave":"010"},\n{"name":"golden.bad\\qname","wave":"000"}\n]}')
    result = symbolic_inputs(file, {"clk"})
    assert result == {"signal": [{"name": "clk", "wave": "010"}]}
    assert "bad\\qname" in file.read_text()
