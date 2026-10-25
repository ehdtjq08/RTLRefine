"""Model orders IDs; all locations and dependency facts are machine-owned."""
import json

from ..model_client import NebiusClient
from .model import MODEL,MAX_TOKENS,SETTINGS,messages as evidence_messages


def schema(ids):
    return {'type':'object','properties':{
        'ranking':{'type':'array','minItems':1,'maxItems':8,'items':{'type':'object','properties':{
            'id':{'type':'string','enum':ids},'mechanism':{'type':'string'}},'required':['id','mechanism'],'additionalProperties':False}},
        'explanation':{'type':'string'}},'required':['ranking','explanation'],'additionalProperties':False}


class EvidenceClient(NebiusClient):
    def __init__(self,ids,ports):
        super().__init__(settings=SETTINGS,timeout=SETTINGS.api_timeout_seconds);self.model_id=MODEL;self.schema=schema(ids)
    def _request(self,endpoint,payload=None):
        if endpoint=='chat/completions' and payload is not None:
            payload={**payload,'response_format':{'type':'json_schema','json_schema':{'name':'machine_anchored_patch_ids','strict':True,'schema':self.schema}}}
        return super()._request(endpoint,payload)


def messages(case,source,deps,cards,discovery,include_evidence=True):
    result=evidence_messages(case,source,deps,cards,discovery,include_evidence)
    result[0]['content']='''Rank at most eight existing patch IDs using the public failure, original source and supplied candidate menu.
Return ranking items {id, mechanism}, plus explanation. Never write RTL, invent candidates, test results, source citations or confidence probabilities.
Source locations, observed failure ports and dependency ranges are attached by the machine, not by your answer. Your mechanism is an unverified hypothesis.
The menu order is arbitrary. Static dependencies are bounded overapproximations, not dynamic causal proof. Related-site scope is a structural preference, not a correctness guarantee.
There is no forced prefix. Candidates and the eight-check budget are identical across methods. No corrected target, candidate outcome, private audit, other view or label is provided.'''
    return result


def parse(response,cards,ports):
    choice=response['choices'][0]
    if choice.get('finish_reason')!='stop':raise ValueError('Incomplete ID ranking')
    value=json.loads(choice['message']['content']);by={c['id']:c for c in cards}
    if not isinstance(value,dict) or set(value)!={'ranking','explanation'} or not isinstance(value['ranking'],list) or not 1<=len(value['ranking'])<=8 or not isinstance(value['explanation'],str):raise ValueError('Invalid ID schema')
    seen=set()
    for r in value['ranking']:
        if not isinstance(r,dict) or set(r)!={'id','mechanism'} or r['id'] not in by or r['id'] in seen or not isinstance(r['mechanism'],str):raise ValueError('Invalid patch ID')
        seen.add(r['id'])
    return value


def recover_id_order_only(response,cards):
    """Separate pre-scoring diagnostic of old raw responses, not a new inference.

    Model-provided source/port citations are retained as claims but ignored.
    Only existing unique IDs in the first eight ranked items are admissible.
    The amendment must be recorded before opening outcome labels.
    """
    choice=response['choices'][0]
    if choice.get('finish_reason')!='stop':raise ValueError('Incomplete raw response')
    value=json.loads(choice['message']['content']);ranking=value.get('ranking')
    if not isinstance(ranking,list) or not ranking:raise ValueError('Missing ranked IDs')
    allowed={c['id'] for c in cards};ids=[]
    for item in ranking[:8]:
        identity=item.get('id') if isinstance(item,dict) else None
        if identity not in allowed or identity in ids:raise ValueError('Unsupported or duplicate ranked ID')
        ids.append(identity)
    return ids
