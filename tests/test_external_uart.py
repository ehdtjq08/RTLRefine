import copy
import json
from pathlib import Path

import pytest

from rtl_agent.common import ROOT
from rtl_agent.uart_external.contract import DATA, VENDOR, DISCOVERY, split_source, source_policy
from rtl_agent.uart_external.agent import messages, parse_proposal
from rtl_agent.uart_external.evaluator import evaluate, feedback, discovery_gate
from rtl_agent.uart_external.simulation import simulate
from rtl_agent.sequential.runner import SequentialRunner
from rtl_agent.tool_paths import find_tool


@pytest.fixture
def runner(tmp_path):
    if not all(find_tool(n) for n in ("yosys", "iverilog", "vvp", "bwrap", "prlimit")):
        pytest.skip("Optional isolated EDA tools unavailable")
    r = SequentialRunner(timeout=60)
    ok, why = r.probe(tmp_path / "probe")
    if not ok:
        pytest.skip(why)
    return r


def test_spec_checker_never_reads_vendor_or_other_rtl(tmp_path, runner, monkeypatch):
    source = (VENDOR / "maintainer_fixed/txuart.v").read_text()
    original_text, original_bytes = Path.read_text, Path.read_bytes
    def deny(path):
        if path.resolve().is_relative_to((ROOT / "third_party").resolve()) or path.resolve().is_relative_to((ROOT / "research").resolve()):
            pytest.fail("Evaluator read an external source or corrected RTL")
    def read_text(path, *a, **k):
        deny(path)
        return original_text(path, *a, **k)
    def read_bytes(path, *a, **k):
        deny(path)
        return original_bytes(path, *a, **k)
    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    result = evaluate(source, tmp_path / "control", runner=runner)
    assert result["accepted"] and not result["fixed_reference_rtl_used"] and not result["synthetic_challenge"]
    assert len(result["discovery_simulations"]) == len(result["audit_simulations"]) == 6
    assert all(s["coverage"]["complete_serial_frames"] == 24 for k in ("discovery_simulations", "audit_simulations") for s in result[k])
    altered = copy.deepcopy(result)
    altered["accepted"] = False
    for simulation in altered["audit_simulations"]:
        simulation["passed"] = False
        simulation["first_violations"] = [{"audit_secret": "do_not_send"}]
    assert discovery_gate(altered) and feedback(result) == feedback(altered)


def test_original_reproduces_blocked_receiver_acceptance_but_disabled_flow_works(tmp_path, runner):
    source = (VENDOR / "buggy/txuart.v").read_text()
    bad = simulate(source, tmp_path / "blocked", runner, DISCOVERY[0], True)
    assert not bad["passed"] and bad["coverage"]["blocked_receiver_accepts"] == 2
    assert any(v["kind"] == "byte_accepted_while_receiver_blocks" for v in bad["first_violations"])
    control = simulate(source, tmp_path / "flow_disabled", runner, DISCOVERY[0], False)
    assert control["passed"] and control["coverage"]["complete_serial_frames"] == 24


def test_always_busy_cannot_pass_without_transmitting(tmp_path, runner):
    source = (VENDOR / "buggy/txuart.v").read_text().replace("assign\to_busy = (r_busy);", "assign\to_busy = 1'b1;")
    assert "assign\to_busy = 1'b1;" in source
    source_policy(source)
    result = simulate(source, tmp_path / "vacuous", runner, DISCOVERY[0], True)
    assert not result["passed"] and any(v["kind"] == "forward_progress_failed" for v in result["first_violations"])


def test_policy_preserves_license_initial_state_and_excludes_checker_controls():
    source = (VENDOR / "buggy/txuart.v").read_text()
    source_policy(source)
    prefix, body, suffix = split_source(source)
    for addition in ("always @(*) assume(1'b0);", "assign i_cts_n=1'b0;", "initial r_busy=0;", 'initial $readmemh("fixed.v", lcl_data);',
                     "wire other = property_top.age;", "// synopsys translate_off\nassign o_busy=0;"):
        with pytest.raises(ValueError):
            source_policy(prefix + body + addition + "\n" + suffix)
    with pytest.raises(ValueError):
        source_policy(source.replace("Copyright (C)", "Changed copyright", 1))


def test_patch_schema_requires_exact_unique_production_edits_and_no_control_leaks():
    source = (VENDOR / "buggy/txuart.v").read_text()
    encoded = json.dumps(messages(source))
    for hidden in ("07e4c47166f0407c276bee571900ed2f9df06bad", "maintainer_fixed", "7403", "8501", "9601"):
        assert hidden not in encoded
    def response(proposal):
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(proposal)}}]}
    proposal, unchanged = parse_proposal(response({"decision": "keep", "edits": [], "explanation": "ok"}), source)
    assert unchanged == source
    for edit in ({"old": "r_busy", "new": "other"}, {"old": "missing substring", "new": "x"},
                 {"old": "Copyright (C) 2015-2019", "new": "no license"}):
        with pytest.raises(ValueError):
            parse_proposal(response({"decision": "repair", "edits": [edit], "explanation": "bad"}), source)
    with pytest.raises(ValueError):
        parse_proposal(response({"decision": "keep", "edits": [{"old": "old", "new": "new"}], "explanation": "bad"}), source)


def test_production_boundary_accepts_indentation_without_relaxing_interface():
    source = (VENDOR / "buggy/txuart.v").read_text()
    prefix, body, suffix = split_source(source)
    unindented = prefix + body.lstrip("\t ") + suffix
    source_policy(unindented)
    assert split_source(unindented)[0] == prefix
    with pytest.raises(ValueError):
        source_policy(unindented.replace("clocks_per_baud, break_condition;", "clocks_per_baud, other_condition;", 1))
    with pytest.raises(ValueError):
        source_policy(unindented.replace("input\twire\t\ti_cts_n;", "input\twire\t\tchanged_cts;", 1))
