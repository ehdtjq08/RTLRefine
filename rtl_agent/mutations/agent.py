"""Isolated-context mutation repair: contract and candidate only, never the truth map."""
from __future__ import annotations

import json
import re

from ..model_client import NebiusClient
from ..model_settings import ModelSettings
from .contract import specification

MODEL = "nvidia/Nemotron-3-Ultra-550b-a55b"
MAX_TOKENS = 16384
SETTINGS = ModelSettings(enable_thinking=True)
SCHEMA = {"type": "object", "properties": {"decision": {"type": "string", "enum": ["keep", "repair"]},
          "rtl": {"type": "string"}, "explanation": {"type": "string"}},
          "required": ["decision", "rtl", "explanation"], "additionalProperties": False}


class MutationClient(NebiusClient):
    def __init__(self):
        super().__init__(settings=SETTINGS, timeout=SETTINGS.api_timeout_seconds)
        self.model_id = MODEL

    def _request(self, endpoint, payload=None):
        if endpoint == "chat/completions" and payload is not None:
            payload = {**payload, "response_format": {"type": "json_schema", "json_schema": {
                "name": "contract_checked_rtl_repair", "strict": True, "schema": SCHEMA}}}
        return super()._request(endpoint, payload)


def canonical(source):
    return re.sub(r"\s+", "", re.sub(r"/\*.*?\*/|//[^\n]*", " ", source, flags=re.S))


def parse_proposal(response, original):
    choice = response["choices"][0]
    if choice.get("finish_reason") != "stop":
        raise ValueError("Model response did not finish")
    proposal = json.loads(choice["message"]["content"])
    if (not isinstance(proposal, dict) or set(proposal) != {"decision", "rtl", "explanation"}
            or proposal["decision"] not in ("keep", "repair") or not isinstance(proposal["rtl"], str)
            or not isinstance(proposal["explanation"], str)):
        raise ValueError("Unexpected proposal schema")
    if proposal["decision"] == "keep" and canonical(proposal["rtl"]) != canonical(original):
        raise ValueError("A keep decision may not change functional source tokens")
    return proposal


def messages(source, *, previous=None, observations=None):
    system = '''Review this Verilog 2001 queue against the supplied behavioral contract.
This is an explicitly synthetic challenge: individual inputs may be healthy or
contain intentionally injected faults. You are not told which, how many, or where.
Return decision=keep if no repair is required, otherwise decision=repair. Return
the COMPLETE Verilog source in rtl and a concise explanation. Keep the MIT SPDX
line and public module parameters/ports. Header whitespace may vary. Do not
refactor healthy code. No added initial blocks, system tasks, macros, assertions,
assumptions, hierarchy access, extra modules, delays or unknown literals. Do not
drive input ports. Ordinary synthesizable registers, arrays and loops are allowed.
You receive no pristine implementation, mutation operator, edit map, clean-file
path or location hint. An independent Python queue and specification properties
will check behavior; they do not compare to a fixed RTL implementation. A second
set of simulation seeds remains unavailable to this repair context.
Required JSON output schema:\n''' + json.dumps(SCHEMA)
    prompt = [{"role": "system", "content": system}, {"role": "user", "content": "Behavioral contract:\n" + json.dumps(specification()) + "\nCandidate RTL:\n" + source}]
    if previous is not None:
        prompt.append({"role": "assistant", "content": json.dumps(previous)})
        prompt.append({"role": "user", "content": "Re-evaluate the same original candidate and contract using these independent discovery observations. Return your best complete source and decision.\n" + json.dumps(observations)})
    return prompt
