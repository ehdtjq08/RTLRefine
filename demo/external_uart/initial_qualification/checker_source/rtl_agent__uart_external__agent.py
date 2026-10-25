"""NVIDIA patch proposals; upstream correction never enters model context."""
from __future__ import annotations

import json

from ..model_client import NebiusClient
from ..model_settings import ModelSettings
from .contract import specification, split_source

MODEL = "nvidia/Nemotron-3-Ultra-550b-a55b"
MAX_TOKENS = 16384
SETTINGS = ModelSettings(enable_thinking=True)
SCHEMA = {"type": "object", "properties": {
    "decision": {"type": "string", "enum": ["keep", "repair"]},
    "edits": {"type": "array", "items": {"type": "object", "properties": {"old": {"type": "string"}, "new": {"type": "string"}}, "required": ["old", "new"], "additionalProperties": False}},
    "explanation": {"type": "string"}}, "required": ["decision", "edits", "explanation"], "additionalProperties": False}


class UartClient(NebiusClient):
    def __init__(self):
        super().__init__(settings=SETTINGS, timeout=SETTINGS.api_timeout_seconds)
        self.model_id = MODEL

    def _request(self, endpoint, payload=None):
        if endpoint == "chat/completions" and payload is not None:
            payload = {**payload, "response_format": {"type": "json_schema", "json_schema": {
                "name": "external_uart_contract_review", "strict": True, "schema": SCHEMA}}}
        return super()._request(endpoint, payload)


def parse_proposal(response, source):
    choice = response["choices"][0]
    if choice.get("finish_reason") != "stop":
        raise ValueError("Incomplete model response")
    proposal = json.loads(choice["message"]["content"])
    if (not isinstance(proposal, dict) or set(proposal) != {"decision", "edits", "explanation"}
            or proposal["decision"] not in ("keep", "repair") or not isinstance(proposal["edits"], list)
            or len(proposal["edits"]) > 6 or not isinstance(proposal["explanation"], str)):
        raise ValueError("Unexpected UART patch schema")
    if proposal["decision"] == "keep" and proposal["edits"]:
        raise ValueError("Keep must contain no edits")
    if proposal["decision"] == "repair" and not proposal["edits"]:
        raise ValueError("Repair requires an actual edit")
    prefix, body, suffix = split_source(source)
    for edit in proposal["edits"]:
        if (not isinstance(edit, dict) or set(edit) != {"old", "new"}
                or not all(isinstance(edit[k], str) and len(edit[k].encode()) <= 6000 for k in ("old", "new"))
                or not edit["old"] or edit["old"] == edit["new"] or body.count(edit["old"]) != 1):
            raise ValueError("Every edit must match exactly once in the production body")
        body = body.replace(edit["old"], edit["new"], 1)
    return proposal, prefix + body + suffix


def messages(source, *, previous=None, observations=None):
    system = '''Review a third-party UART transmitter against its public behavioral contract.
Decide keep if it meets the contract, repair if a change is needed. Return up to
six exact old/new substring replacements in the production body, not a rewritten
file. Preserve copyright/license, ports, parameters, initial assignments and the
disabled `ifdef FORMAL appendix. Keep production logic synchronous to posedge
i_clk. No new tasks, functions, directives, hierarchy, assertions, assumptions,
delays, unknown literal assignments, input drivers or extra modules. Each old
substring must occur exactly once; tabs and newlines must match exactly. Avoid
unrelated refactors. The serial protocol, CTS safety and forward progress are
checked independently from external ports. You receive no corrected source,
maintainer patch, commit ID, issue description or unexposed audit results.
This single selected historical example is not an unseen benchmark; the public
code may have appeared in model training. JSON schema:\n''' + json.dumps(SCHEMA)
    result = [{"role": "system", "content": system}, {"role": "user", "content": "Behavioral contract:\n" + json.dumps(specification()) + "\nOriginal candidate RTL:\n" + source}]
    if previous is not None:
        result += [{"role": "assistant", "content": json.dumps(previous)}, {"role": "user", "content":
            "Reconsider the same ORIGINAL source using these discovery observations. All edits apply to the original, not your prior proposal.\n" + json.dumps(observations)}]
    return result
