"""Line-range proposals against the original; no whitespace substring guessing."""
from __future__ import annotations

import json

from ..model_client import NebiusClient
from ..model_settings import ModelSettings
from .cases import code_only, public_contract

MODEL = "nvidia/Nemotron-3-Ultra-550b-a55b"
MAX_TOKENS = 24576
SETTINGS = ModelSettings(enable_thinking=True)
SCHEMA = {"type": "object", "properties": {
    "decision": {"type": "string", "enum": ["keep", "repair"]},
    "edits": {"type": "array", "items": {"type": "object", "properties": {
        "start_line": {"type": "integer"}, "end_line": {"type": "integer"}, "replacement": {"type": "string"}},
        "required": ["start_line", "end_line", "replacement"], "additionalProperties": False}},
    "explanation": {"type": "string"}}, "required": ["decision", "edits", "explanation"], "additionalProperties": False}


class KnownBugClient(NebiusClient):
    def __init__(self):
        super().__init__(settings=SETTINGS, timeout=SETTINGS.api_timeout_seconds)
        self.model_id = MODEL

    def _request(self, endpoint, payload=None):
        if endpoint == "chat/completions" and payload is not None:
            payload = {**payload, "response_format": {"type": "json_schema", "json_schema": {
                "name": "original_rtl_line_edits", "strict": True, "schema": SCHEMA}}}
        return super()._request(endpoint, payload)


def apply_proposal(proposal, original):
    if (not isinstance(proposal, dict) or set(proposal) != {"decision", "edits", "explanation"}
            or proposal["decision"] not in ("keep", "repair") or not isinstance(proposal["edits"], list)
            or len(proposal["edits"]) > 12 or not isinstance(proposal["explanation"], str)):
        raise ValueError("Unexpected line-edit schema")
    if proposal["decision"] == "keep" and proposal["edits"]:
        raise ValueError("Keep requires no source edits")
    if proposal["decision"] == "repair" and not proposal["edits"]:
        raise ValueError("Repair requires at least one edit")
    lines = original.splitlines(keepends=True)
    start = original.count("\n", 0, original.index(");") + 2) + 2
    intervals = []
    for edit in proposal["edits"]:
        if (not isinstance(edit, dict) or set(edit) != {"start_line", "end_line", "replacement"}
                or type(edit["start_line"]) is not int or type(edit["end_line"]) is not int
                or not start <= edit["start_line"] <= edit["end_line"] <= len(lines)
                or not isinstance(edit["replacement"], str) or len(edit["replacement"].encode()) > 16000):
            raise ValueError("Invalid line interval or replacement size")
        intervals.append((edit["start_line"], edit["end_line"], edit["replacement"]))
    intervals.sort()
    if any(a[1] >= b[0] for a, b in zip(intervals, intervals[1:])):
        raise ValueError("Edits must not overlap")
    for first, last, text in reversed(intervals):
        # Declared line-block semantics, never a functional controller repair.
        replacement = text + "\n" if text and not text.endswith("\n") else text
        lines[first - 1:last] = [replacement]
    return "".join(lines)


def parse_proposal(response, original):
    choice = response["choices"][0]
    if choice.get("finish_reason") != "stop":
        raise ValueError("Model did not complete its JSON response")
    proposal = json.loads(choice["message"]["content"])
    return proposal, apply_proposal(proposal, original)


def messages(case, original, dependencies, *, previous=None, observations=None):
    system = '''Review an original Verilog module against the supplied public role and
fixed-configuration behavior. Candidates can be healthy or contain a historical
defect; you receive no label, corrected RTL, maintainer patch or audit result.
Return decision=keep with edits=[] if no functional repair is needed, otherwise
decision=repair with up to 12 line-range replacements. Line numbers refer to the
ORIGINAL editable file, including blank lines; start_line/end_line are inclusive.
Replacements are complete line blocks; a missing final newline is appended by
the patch applicator. No functional change is made by the controller.
Preserve the exact license/interface prefix, public ports, parameter defaults,
compiler directives and module names. Do not edit dependencies. New plain reg
declarations and synthesizable constant initial assignments are allowed where
needed. No runtime system tasks/file reads, hierarchy, functions/tasks, new
clocking event forms, timing delays, assumptions/assertions, compiler pragmas,
input drivers or extra modules. Avoid unrelated refactors. Public historical
code can have appeared in model training; this is not an unseen benchmark.
Return only the JSON schema:\n''' + json.dumps(SCHEMA)
    text = code_only(original)
    numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(text.splitlines(), 1))
    editable_start = original.count("\n", 0, original.index(");") + 2) + 2
    prompt = [{"role": "system", "content": system}, {"role": "user", "content":
        "Public contract:\n" + json.dumps(public_contract(case)) + f"\nFirst editable line: {editable_start}. All earlier lines are immutable.\nOriginal editable file (numbered):\n" + numbered +
        "\nRead-only dependencies (comments omitted):\n" + code_only(dependencies)}]
    if previous is not None:
        prompt.append({"role": "assistant", "content": json.dumps(previous)})
        if observations is None:
            prompt.append({"role": "user", "content": "Independently reconsider your first proposal against the same public contract. Check your own logic and return your best decision and edits. All line ranges still apply to the original file. No execution feedback is provided."})
        else:
            prompt.append({"role": "user", "content": "Reconsider your first proposal using these DISCOVERY-only external observations. Return your best decision and edits against the original file.\n" + json.dumps(observations)})
    return prompt
