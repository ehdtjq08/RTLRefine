"""NVIDIA ranks a closed candidate pool; it cannot write or change RTL."""
from __future__ import annotations

import json

from ..model_client import NebiusClient
from ..model_settings import ModelSettings
from ..known_bugs_v2.cases import code_only, public_contract

MODEL = "nvidia/Nemotron-3-Ultra-550b-a55b"
MAX_TOKENS = 4096
SETTINGS = ModelSettings(enable_thinking=False)


def schema(ids):
    return {"type":"object","properties":{
        "ranked_ids":{"type":"array","items":{"type":"string","enum":ids}},
        "explanation":{"type":"string"}},"required":["ranked_ids","explanation"],"additionalProperties":False}


class RankingClient(NebiusClient):
    def __init__(self, ids):
        super().__init__(settings=SETTINGS,timeout=SETTINGS.api_timeout_seconds)
        self.model_id=MODEL
        self.ids=ids

    def _request(self, endpoint, payload=None):
        if endpoint=="chat/completions" and payload is not None:
            payload={**payload,"response_format":{"type":"json_schema","json_schema":{
                "name":"rank_existing_rtl_candidates","strict":True,"schema":schema(self.ids)}}}
        return super()._request(endpoint,payload)


def messages(case, source, dependencies, pool, discovery_feedback):
    menu=[]
    for item in pool:
        menu.append({"id":item["id"],"family":item["family"],"line":item["line"],"note":item["note"],
                     "edits":[{"old":e["old"],"replacement":e["replacement"]} for e in item["edits"]]})
    return [{"role":"system","content":'''Rank existing small RTL repair candidates using the public contract and discovery observations.
You may only return candidate IDs from the menu, in descending likelihood of correcting the defect.
Return at most eight distinct IDs and a concise explanation. Do not write RTL or invent IDs.
Two source-order candidates are always tried first for BOTH methods. Your ranking orders later tests;
unlisted IDs retain their original order. Each method has at most eight candidate evaluations.
No corrected target RTL, audit data, hidden source labels, candidate evaluation outcome or past model
answer is provided. The menu is a restricted lexical edit grammar, not an SMT solver. Public
historical source may have appeared in training. JSON fields: ranked_ids, explanation.'''} ,
            {"role":"user","content":"Public role:\n"+json.dumps(public_contract(case))+
             "\nOriginal editable RTL (comments omitted):\n"+code_only(source)+
             "\nRead-only dependencies (comments omitted):\n"+code_only(dependencies)+
             "\nOriginal source discovery observations only:\n"+json.dumps(discovery_feedback)+
             "\nPre-generated candidate menu (no candidate has been scored yet):\n"+json.dumps(menu)}]


def parse(response, ids):
    choice=response["choices"][0]
    if choice.get("finish_reason")!="stop":
        raise ValueError("Ranking response incomplete")
    value=json.loads(choice["message"]["content"])
    if (not isinstance(value,dict) or set(value)!={"ranked_ids","explanation"}
        or not isinstance(value["ranked_ids"],list) or len(value["ranked_ids"])>8
        or not isinstance(value["explanation"],str)
        or any(not isinstance(i,str) or i not in ids for i in value["ranked_ids"])
        or len(set(value["ranked_ids"]))!=len(value["ranked_ids"])):
        raise ValueError("Invalid or duplicate ranked ID")
    return value


def guided_order(ids, ranked_ids, prefix=2):
    result=list(ids[:prefix])
    result += [i for i in ranked_ids if i not in result]
    result += [i for i in ids if i not in result]
    return result
