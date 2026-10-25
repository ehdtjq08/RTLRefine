"""Application orchestration; no model request is made while browsing."""
from __future__ import annotations

import json
from pathlib import Path

from rtl_agent.common import ROOT, new_run_dir, sha256, write_json
from rtl_agent.model_client import ModelError
from rtl_agent.sequential.case_agent import CaseClient, MAX_TOKENS, messages
from rtl_agent.sequential.case_review import evaluate, feedback, get_case, original_source, review, source_policy


def recorded_candidate(case_id):
    if case_id == "fifo_reset":
        folder = ROOT / "demo/fifo_reset"
        record = json.loads((folder / "current.json").read_text())
        return (folder / record["accepted_rtl"]).read_text(), "Recorded NVIDIA repair; verified within the recorded bound"
    if case_id == "axis_keep":
        folder = ROOT / "demo/adapter_keep"
        record = json.loads((folder / "current.json").read_text())
        return (folder / record["review_rtl"]).read_text(), "Recorded NVIDIA partial repair; rejected by the independent checker"
    file = ROOT / "demo/sequential_cases/frame_fifo/selected_candidate.v"
    if file.is_file():
        return file.read_text(), "Recorded NVIDIA candidate; run the checks to inspect its result"
    return original_source(case_id), "No packaged NVIDIA candidate yet; historical original loaded"


def snapshot(directory):
    folder = Path(directory) / "controller_source"
    folder.mkdir(exist_ok=True)
    hashes = {}
    files = sorted((ROOT / "rtl_agent/sequential").glob("*.py"))
    files += [ROOT / "workspace_service.py"]
    for file in files:
        name = str(file.relative_to(ROOT)).replace("/", "__")
        content = file.read_bytes()
        (folder / name).write_bytes(content)
        hashes[str(file.relative_to(ROOT))] = sha256(content)
    write_json(Path(directory) / "controller_hashes.json", hashes)


def check_change(case_id, source):
    result = review(case_id, source)
    snapshot(result["directory"])
    return result


def request_repair(case_id, source, previous_review):
    source_policy(case_id, source)
    if (previous_review["case"] != case_id or previous_review["rtl_sha256"] != sha256(source.encode())
            or previous_review["accepted"]):
        raise ValueError("First run independent checks on the current failing source")
    get_case(case_id)
    directory = new_run_dir("workspace_nvidia_repair")
    snapshot(directory)
    client = CaseClient()
    client.verify_model()
    prompt = messages(case_id, previous_review, previous={"rtl": source, "explanation": "Designer-submitted failing candidate"},
                      observations=feedback(previous_review, previous_review["directory"]))
    write_json(directory / "messages.json", prompt)
    result = {"status": "MODEL_RESPONSE_ERROR", "case": case_id, "accepted": False, "directory": str(directory)}
    try:
        response = client.generate(prompt, max_tokens=MAX_TOKENS)
        write_json(directory / "response.json", response)
        choice = response["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise ValueError("The model response did not finish; no candidate was accepted")
        proposal = json.loads(choice["message"]["content"])
        if not isinstance(proposal, dict) or set(proposal) != {"rtl", "explanation"} or not all(isinstance(proposal[k], str) for k in proposal):
            raise ValueError("Unexpected proposal schema")
        write_json(directory / "proposal.json", proposal)
        checked = evaluate(case_id, proposal["rtl"], directory / "review")
        snapshot(checked["directory"])
        result.update({"status": checked["status"], "accepted": checked["accepted"], "review": checked, "proposal": proposal})
    except (ModelError, ValueError, OSError, KeyError, IndexError, TypeError) as exc:
        result["error"] = client.redact(str(exc))
    result["cost"] = client.last_cost
    write_json(directory / "model_run.json", result)
    return result
