"""One reasoning request: diagnose the public witness and prioritize real IDs."""
import json
import time

from ..budget import BudgetLedger
from ..common import write_json
from ..evidence_ranking.model import messages as evidence_messages,MODEL
from ..model_client import NebiusClient
from ..model_settings import ModelSettings

MAX_TOKENS=12288
SETTINGS=ModelSettings(enable_thinking=True)


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
    prompt=evidence_messages(case,source,dependencies,cards,discovery,True)
    prompt[0]['content']='''Diagnose the observed public RTL failure and prioritize up to six EXISTING patch IDs.
First reason through the signal's intended lifetime and control flow, transfers, reset and end-of-frame behavior using the actual source and public input window. A reset-looking symptom does not by itself identify a reset bug.
Explain a concrete mechanism linking the source to the observed mismatch. Treat static dependency ranges as coarse evidence, never causal proof. Your diagnosis is an unverified hypothesis until independent checks pass.
The menu has no candidate execution outcomes, corrected RTL or private audit data. Do not write code, invent IDs, assert test results or provide confidence probabilities. Return {diagnosis, ranking:[{id,mechanism}]}. A complete deterministic search tail remains available if your first hypotheses fail.'''
    write_json(directory/'messages.json',prompt)
    ledger=BudgetLedger();remaining=ledger.summary();quote=ledger.quote(MODEL,MAX_TOKENS)
    if quote['reserved_usd']>min(4.,remaining['remaining_usd'],remaining['phase_remaining_usd']):raise ValueError('Cannot reserve one bounded diagnosis request')
    client=DiagnosisClient([c['id'] for c in cards]);client.verify_model();start=time.monotonic()
    write_json(directory/'request_started.json',{'api_requests_max':1,'automatic_retry':False})
    result={'status':'ERROR','ids':[],'diagnosis':None}
    try:
        response=client.generate(prompt,max_tokens=MAX_TOKENS);write_json(directory/'response.json',response)
        choice=response['choices'][0]
        if choice.get('finish_reason')!='stop':raise ValueError('Diagnosis response incomplete')
        value=json.loads(choice['message']['content']);allowed={c['id'] for c in cards}
        if not isinstance(value,dict) or set(value)!={'diagnosis','ranking'} or not isinstance(value['diagnosis'],str) or not isinstance(value['ranking'],list) or not 1<=len(value['ranking'])<=6:raise ValueError('Unexpected diagnosis schema')
        ids=[]
        for item in value['ranking']:
            if set(item)!={'id','mechanism'} or item['id'] not in allowed or item['id'] in ids or not isinstance(item['mechanism'],str):raise ValueError('Invalid hypothesis ID')
            ids.append(item['id'])
        result.update({'status':'VALID','ids':ids,'diagnosis':value['diagnosis'],'proposal':value})
    except Exception as exc:result['error']=client.redact(type(exc).__name__+': '+str(exc))
    result.update({'api_requests':client.inference_requests,'cost':client.last_cost,'wall_seconds':time.monotonic()-start})
    write_json(directory/'diagnosis.json',result);return result
