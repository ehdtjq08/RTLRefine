"""One reasoning request: diagnose the public witness and prioritize real IDs."""
import json
import time

from ..budget import BudgetLedger
from ..common import write_json
from ..evidence_ranking.model import MODEL
from ..known_bugs_v2.cases import code_only,public_contract
from ..model_client import NebiusClient
from ..model_settings import ModelSettings

MAX_TOKENS=4096
SETTINGS=ModelSettings(enable_thinking=False)


class DiagnosisClient(NebiusClient):
    def __init__(self,ids):
        super().__init__(settings=SETTINGS,timeout=SETTINGS.api_timeout_seconds);self.model_id=MODEL
        self.schema={'type':'object','properties':{'diagnosis':{'type':'string'},
            'ranking':{'type':'array','minItems':1,'maxItems':6,'items':{'type':'object','properties':{
                'id':{'type':'string','enum':ids},'mechanism':{'type':'string'}},'required':['id','mechanism'],'additionalProperties':False}}},
            'required':['diagnosis','ranking'],'additionalProperties':False}
    def _request(self,endpoint,payload=None):
        if endpoint=='chat/completions' and payload is not None:
            payload={**payload,'response_format':{'type':'json_schema','json_schema':{'name':'rtl_failure_diagnosis','strict':True,'schema':self.schema}}}
        return super()._request(endpoint,payload)


def diagnose(case,source,dependencies,cards,discovery,directory):
    directory.mkdir()
    labels={c['legacy_id']:c['id'] for c in cards}
    menu=[{'id':c['legacy_id'],'family':c['family'],'line':c['line'],'note':c['note'],
        'edits':[{'old':e['old'],'replacement':e['replacement']} for e in c['edits']]} for c in cards]
    trace=discovery['traces'][0]
    observed={k:trace[k] for k in ('cycles','mismatch_count','first_mismatches','input_windows') if k in trace}
    observed['first_mismatches']=observed.get('first_mismatches',[])[:3]
    observed['input_windows']=observed.get('input_windows',[])[:1]
    prompt=[{'role':'system','content':'''Diagnose the observed public RTL failure and prioritize up to six EXISTING patch IDs.
First reason through the signal's intended lifetime and control flow, transfers, reset and end-of-frame behavior using the actual source and public input window. A reset-looking symptom does not by itself identify a reset bug.
Explain a concrete mechanism linking the source to the observed mismatch. Treat static dependency ranges as coarse evidence, never causal proof. Your diagnosis is an unverified hypothesis until independent checks pass.
The menu has no candidate execution outcomes, corrected RTL or private audit data. Do not write code, invent IDs, assert test results or provide confidence probabilities. Return {diagnosis, ranking:[{id,mechanism}]}. Keep the diagnosis to two clear sentences. A complete deterministic search tail remains available if your first hypotheses fail.'''},
        {'role':'user','content':'Public role:\n'+json.dumps(public_contract(case))+'\nOriginal source:\n'+code_only(source)+
         '\nDependencies:\n'+code_only(dependencies)+'\nPublic failure:\n'+json.dumps(observed)+'\nExisting hypotheses:\n'+json.dumps(menu)}]
    write_json(directory/'messages.json',prompt)
    ledger=BudgetLedger();remaining=ledger.summary();quote=ledger.quote(MODEL,MAX_TOKENS)
    if quote['reserved_usd']>min(4.,remaining['remaining_usd'],remaining['phase_remaining_usd']):raise ValueError('Cannot reserve one bounded diagnosis request')
    client=DiagnosisClient(list(labels));client.verify_model();start=time.monotonic()
    write_json(directory/'request_started.json',{'api_requests_max':1,'automatic_retry':False})
    result={'status':'ERROR','ids':[],'diagnosis':None}
    try:
        response=client.generate(prompt,max_tokens=MAX_TOKENS);write_json(directory/'response.json',response)
        choice=response['choices'][0]
        if choice.get('finish_reason')!='stop':raise ValueError('Diagnosis response incomplete')
        value=json.loads(choice['message']['content']);allowed=set(labels)
        if not isinstance(value,dict) or set(value)!={'diagnosis','ranking'} or not isinstance(value['diagnosis'],str) or not isinstance(value['ranking'],list) or not 1<=len(value['ranking'])<=6:raise ValueError('Unexpected diagnosis schema')
        ids=[]
        for item in value['ranking']:
            if set(item)!={'id','mechanism'} or item['id'] not in allowed or item['id'] in ids or not isinstance(item['mechanism'],str):raise ValueError('Invalid hypothesis ID')
            ids.append(item['id'])
        result.update({'status':'VALID','ids':[labels[i] for i in ids],'display_ids':ids,'diagnosis':value['diagnosis'],'proposal':value})
    except Exception as exc:result['error']=client.redact(type(exc).__name__+': '+str(exc))
    result.update({'api_requests':client.inference_requests,'cost':client.last_cost,'wall_seconds':time.monotonic()-start})
    write_json(directory/'diagnosis.json',result);return result
