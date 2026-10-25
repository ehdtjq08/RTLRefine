"""Full-source NVIDIA proposals under the same independent review boundary."""
from __future__ import annotations

import json

from ..model_client import NebiusClient
from ..model_settings import ModelSettings
from .case_review import get_case, original_source, simulation_summary

MODEL = "nvidia/Nemotron-3-Ultra-550b-a55b"
MAX_TOKENS = 16384
SETTINGS = ModelSettings(enable_thinking=True)
SCHEMA = {"type": "object", "properties": {"rtl": {"type": "string"}, "explanation": {"type": "string"}},
          "required": ["rtl", "explanation"], "additionalProperties": False}


class CaseClient(NebiusClient):
    def __init__(self):
        super().__init__(settings=SETTINGS, timeout=SETTINGS.api_timeout_seconds)
        self.model_id = MODEL

    def _request(self, endpoint, payload=None):
        if endpoint == "chat/completions" and payload is not None:
            payload = {**payload, "response_format": {"type": "json_schema", "json_schema": {
                "name": "complete_rtl_candidate", "strict": True, "schema": SCHEMA}}}
        return super()._request(endpoint, payload)


def messages(case_id, baseline, *, previous=None, observations=None):
    case = get_case(case_id)
    system = '''Repair a real historical Verilog module. Return the COMPLETE Verilog
source in the rtl JSON string and a concise explanation. Do not return a diff,
snippets, Markdown fences or pseudocode. Keep the supplied license, module
parameter/port header, compiler directives and existing configuration-checking
initial block byte-identical. Make small synthesizable logic changes. No added
initial blocks, tasks, system calls, hierarchy access, delays, unknown literals,
modules or testbench access. Do not suppress traffic to conceal a failure.
You receive no reference implementation or known patch. A separate independent
checker accepts a candidate only after every directed regression and bounded
reference comparison passes. Current scope is the stated parameterizations,
not all Verilog projects or an unbounded correctness guarantee.
Required JSON output schema:\n''' + json.dumps(SCHEMA)
    user = "Required behavior:\n" + case["contract"] + "\nOriginal RTL:\n" + original_source(case_id)
    user += "\nIndependent baseline simulation observations:\n" + json.dumps([simulation_summary(case_id, s) for s in baseline["simulations"]])
    prompt = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if previous is not None:
        prompt.append({"role": "assistant", "content": json.dumps(previous)})
        if observations is None:
            prompt.append({"role": "user", "content": "Independently review your previous proposal against the original code and required behavior. Return your best complete candidate, correcting any issues you identify. No checker feedback is provided for this step."})
        else:
            prompt.append({"role": "user", "content": "Review your previous proposal using these independent checker observations. Return your best complete candidate.\n" + json.dumps(observations)})
    return prompt
