"""Grounded, order-perturbed ranking over immutable content-addressed cards."""
import json

from ..model_client import NebiusClient
from ..model_settings import ModelSettings
from ..known_bugs_v2.cases import code_only,public_contract

MODEL='nvidia/Nemotron-3-Ultra-550b-a55b'
MAX_TOKENS=6144
SETTINGS=ModelSettings(enable_thinking=False)


def schema(ids,ports):
    return {'type':'object','properties':{
        'ranking':{'type':'array','items':{'type':'object','properties':{
            'id':{'type':'string','enum':ids},'failure_port':{'type':'string','enum':ports},'source_line':{'type':'integer'},
            'mechanism':{'type':'string'}},'required':['id','failure_port','source_line','mechanism'],'additionalProperties':False}},
        'explanation':{'type':'string'}},'required':['ranking','explanation'],'additionalProperties':False}


class EvidenceClient(NebiusClient):
    def __init__(self,ids,ports):
        super().__init__(settings=SETTINGS,timeout=SETTINGS.api_timeout_seconds);self.model_id=MODEL;self.schema=schema(ids,ports)
    def _request(self,endpoint,payload=None):
        if endpoint=='chat/completions' and payload is not None:
            payload={**payload,'response_format':{'type':'json_schema','json_schema':{'name':'evidence_anchored_ranking','strict':True,'schema':self.schema}}}
        return super()._request(endpoint,payload)


def messages(case,source,deps,cards,discovery,include_evidence=True):
    keys=('id','family','line','note','edits','failure_anchors','dependency','structural_coverage','changed_targets','direct_failure_target','heuristic_components') if include_evidence else ('id','family','line','note','edits')
    menu=[{k:c[k] for k in keys} for c in cards]
    # Omit ordinal legacy IDs, including structural-superset names.
    for c in menu:
        if 'structural_coverage' in c:c['structural_coverage']={k:v for k,v in c['structural_coverage'].items() if k!='superset_ids'}
    return [{'role':'system','content':'''Rank at most eight existing RTL patch IDs. You cannot write RTL, invent candidates or change the tests.
Use the public failure, original code and machine evidence. Cite the exact candidate source line and one observed failing output port for each ranked ID.
Static dependency ranges are a bounded overapproximation, not proven dynamic causality. Related multi-site bundles may preserve scope better than a single-lane edit, but extra edits are not automatically correct.
No candidate execution outcome, corrected target source, audit data, other model view or labels are available. IDs are content-addressed and their display order is arbitrary.
Do not copy display order. Describe a specific mechanism linking each patch to its cited failure. One check budget is eight candidates, starting directly with your order; there is no forced source-order prefix.
Return ranking and explanation. Citations and stability are evidence checks, not correctness guarantees.'''},
            {'role':'user','content':'Public profile:\n'+json.dumps(public_contract(case))+'\nOriginal editable source:\n'+code_only(source)+
             '\nRead-only dependencies:\n'+code_only(deps)+'\nOriginal discovery observations:\n'+json.dumps(discovery)+'\nCandidate evidence cards:\n'+json.dumps(menu)}]


def parse(response,cards,ports):
    choice=response['choices'][0]
    if choice.get('finish_reason')!='stop':raise ValueError('Incomplete ranking')
    value=json.loads(choice['message']['content']);by_id={c['id']:c for c in cards}
    if not isinstance(value,dict) or set(value)!={'ranking','explanation'} or not isinstance(value['ranking'],list) or not 1<=len(value['ranking'])<=8 or not isinstance(value['explanation'],str):raise ValueError('Invalid ranking schema')
    seen=set()
    for r in value['ranking']:
        if not isinstance(r,dict) or set(r)!={'id','failure_port','source_line','mechanism'}:raise ValueError('Invalid ranking item')
        if r['id'] not in by_id or r['id'] in seen:raise ValueError('Unknown or repeated ID')
        if r['failure_port'] not in ports or type(r['source_line']) is not int or r['source_line']!=by_id[r['id']]['line'] or not isinstance(r['mechanism'],str):raise ValueError('Unsupported evidence citation')
        seen.add(r['id'])
    return value
