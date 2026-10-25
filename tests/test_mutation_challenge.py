import copy
import json
from pathlib import Path

import pytest

from rtl_agent.common import ROOT
from rtl_agent.mutations.agent import messages, parse_proposal
from rtl_agent.mutations.contract import DATA, source_policy
from rtl_agent.mutations.evaluator import discovery_gate, evaluate, feedback
from rtl_agent.mutations.formal import bounded
from rtl_agent.sequential.runner import SequentialRunner
from rtl_agent.tool_paths import find_tool


@pytest.fixture
def runner(tmp_path):
    if not all(find_tool(name) for name in ("yosys", "iverilog", "vvp", "bwrap", "prlimit")):
        pytest.skip("Optional isolated EDA tools unavailable")
    r = SequentialRunner(timeout=60)
    ok, why = r.probe(tmp_path / "probe")
    if not ok:
        pytest.skip(why)
    return r


def test_specification_checker_accepts_control_without_reading_pristine_or_labels(tmp_path, runner, monkeypatch):
    source = (DATA / "cases/candidate_03/candidate.v").read_text()
    read = Path.read_text
    read_bytes = Path.read_bytes
    def deny_truth(path):
        resolved = path.resolve()
        if resolved.is_relative_to((DATA / "cases").resolve()) or resolved.is_relative_to((ROOT / "research").resolve()):
            pytest.fail("Specification checker read another candidate or author-only source")
    def guarded(path, *args, **kwargs):
        deny_truth(path)
        if path.name in ("clean.v", "mutation_map.json"):
            pytest.fail("Specification checker read evaluation-only truth")
        return read(path, *args, **kwargs)
    def guarded_bytes(path, *args, **kwargs):
        deny_truth(path)
        return read_bytes(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", guarded)
    monkeypatch.setattr(Path, "read_bytes", guarded_bytes)
    result = evaluate(source, tmp_path / "healthy", runner=runner)
    assert result["accepted"] and result["fixed_reference_rtl_used"] is False
    for simulation in result["discovery_simulations"] + result["audit_simulations"]:
        assert simulation["coverage"]["accepted_inputs"] > 20
        assert simulation["coverage"]["simultaneous"] > 0
        assert simulation["coverage"]["flush_nonempty"] > 0
    altered = copy.deepcopy(result)
    altered["status"] = "SIMULATION_FAILED"
    for sim in altered["audit_simulations"]:
        sim["passed"] = False
    assert discovery_gate(altered)
    assert feedback(result) == feedback(altered)


@pytest.mark.parametrize("case_number", range(1, 9))
def test_seeded_faults_and_normal_controls_use_real_interface_observations(case_number, tmp_path, runner):
    from rtl_agent.mutations.simulation import simulate
    from rtl_agent.mutations.contract import DISCOVERY
    source = (DATA / f"cases/candidate_{case_number:02d}/candidate.v").read_text()
    result = simulate(source, tmp_path / "candidate", runner, DISCOVERY[0])
    assert result["passed"] == (case_number in (3, 6))


def test_policy_rejects_weakened_assumptions_input_drivers_and_file_access():
    source = (DATA / "cases/candidate_03/candidate.v").read_text()
    source_policy(source)
    for extra in ("always @* assume(1'b0);", "assign m_ready = 1'b1;", 'initial $readmemh("clean.v", mem);',
                  "wire bad = property_top.expected_count;", "// synopsys translate_off\nassign m_valid=0;"):
        with pytest.raises(ValueError):
            source_policy(source.replace("endmodule", extra + "\nendmodule"))


def test_output_suppression_cannot_win_by_transferring_nothing(tmp_path, runner):
    source = (DATA / "cases/candidate_03/candidate.v").read_text().replace(
        "assign m_valid = !rst && (count != 0);", "assign m_valid = 1'b0;")
    result = evaluate(source, tmp_path / "suppressed", runner=runner)
    assert not result["accepted"]
    assert any(p["status"] == "COUNTEREXAMPLE" for p in result["formal"])
    assert any(v["property"] == "valid_matches_occupancy" for v in result["discovery_simulations"][0]["first_violations"])


def test_selector_is_not_restricted_to_payload_bit_zero(tmp_path, runner):
    truth = json.loads((ROOT / "research/mutation_challenge_v1_author/mutation_map.json").read_text())
    case = next(row for row in truth["cases"] if row["kind"] == "sideband_swap")
    source = (DATA / case["source"]).read_text()
    proof = bounded(source, tmp_path / "sidebands", runner, (1, 16))
    assert proof["status"] == "COUNTEREXAMPLE"
    assert proof["replay"]["status"] == "CONTRACT_FAILURE_REPRODUCED"
    from rtl_agent.mutations.formal import decode_signal
    selector = next(s for s in proof["public_trace"]["signal"] if s["name"] == "watched_bit")
    assert set(v for v in decode_signal(selector)[1:] if v is not None) <= {8, 9}


def test_api_context_and_keep_decision_do_not_smuggle_a_patch_or_audit():
    source = (DATA / "cases/candidate_01/candidate.v").read_text()
    prompt = json.dumps(messages(source))
    assert "mutation_map.json" not in prompt and "candidate_01" not in prompt
    assert "reset_tail_retained" not in prompt and "write_without_acceptance" not in prompt
    assert "7403" not in prompt and "8501" not in prompt
    response = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"decision": "keep", "rtl": source.replace("count <= count;", "count <= 0;"), "explanation": "hidden repair"})}}]}
    with pytest.raises(ValueError, match="keep decision"):
        parse_proposal(response, source)


def test_unexposed_audit_failure_never_causes_an_additional_model_call(tmp_path, monkeypatch):
    import scripts.run_mutation_challenge as driver
    source = (DATA / "cases/candidate_03/candidate.v").read_text()
    class Client:
        last_cost = {"estimated_usd": 0.0}
        calls = 0
        inference_requests = 0
        def generate(self, prompt, max_tokens):
            self.calls += 1
            self.inference_requests += 1
            assert self.calls == 1
            return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"decision": "keep", "rtl": source, "explanation": "Meets contract"})}}]}
        def redact(self, value):
            return value
    monkeypatch.setattr(driver, "MutationClient", Client)
    monkeypatch.setattr(driver, "evaluate", lambda *a, **k: {"status": "SIMULATION_FAILED", "accepted": False,
        "discovery_simulations": [{"passed": True}] * 3, "audit_simulations": [{"passed": False}] * 3,
        "formal": [{"status": "BOUNDED_PROPERTY_PASS"}] * 2})
    dataset = json.loads((DATA / "dataset.json").read_text())
    result = driver.run_case(next(row for row in dataset["cases"] if row["case_id"] == "candidate_03"), tmp_path)
    assert not result["accepted"] and len(result["attempts"]) == 1


def test_recorded_synthetic_ui_distinguishes_repairs_controls_and_no_reference(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr("rtl_agent.mutations.agent.MutationClient.generate", lambda *a, **k: pytest.fail("Unexpected model request"))
    app = AppTest.from_file(str(ROOT / "mutation_app.py"), default_timeout=20).run()
    assert not app.exception
    assert app.title[0].value == "Repair the fault. Keep the contract."
    values = {item.label: item.value for item in app.metric}
    assert values["Injected cases repaired by NVIDIA"] == "6/6"
    assert values["Normal controls kept unchanged"] == "1/2"
    assert all(item.value == "No" for item in app.metric if item.label == "Golden RTL used")
    assert any("constructed mutation experiment" in item.value for item in app.info)
    assert any("NOT ACCEPTED" in item.value for item in app.error)
    assert any("VERIFIED AGAINST SPEC" in item.value for item in app.success)


def test_download_has_checker_source_and_license_but_no_pristine_or_vm_binary():
    import hashlib
    import io
    import zipfile
    import mutation_app
    folder = ROOT / "demo/mutation_challenge/run/candidate_01/attempt_1/evaluation"
    with zipfile.ZipFile(io.BytesIO(mutation_app.evidence(folder))) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert len(archive.namelist()) == len(manifest) + 1
        for name, metadata in manifest.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == metadata["sha256"]
        assert "formal_0/properties.v" in archive.namelist()
        assert "formal_1/properties.v" in archive.namelist()
        assert "checker_source/rtl_agent__mutations__simulation.py" in archive.namelist()
        assert "COPYING" in archive.namelist()
        assert not any(name.endswith(("clean.v", "mutation_map.json", ".vvp")) or ".env" in name for name in archive.namelist())
