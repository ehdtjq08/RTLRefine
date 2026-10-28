"""Real multi-file line patches against public user testbench observations."""
import json
from pathlib import Path
import re
import time

from ..budget import BudgetLedger
from ..common import write_json
from ..model_client import NebiusClient
from ..model_settings import ModelSettings
from ..evidence_ranking.model import MODEL
from .policy import tokens,apply_edits,interfaces

MAX_TOKENS=6144
SETTINGS=ModelSettings(enable_thinking=False)


class ProjectClient(NebiusClient):
    def __init__(self,files):
        super().__init__(settings=SETTINGS,timeout=120);self.model_id=MODEL
        self.schema={'type':'object','properties':{'diagnosis':{'type':'string'},'edits':{'type':'array','minItems':1,'maxItems':12,'items':{
            'type':'object','properties':{'file':{'type':'string','enum':files},'start_line':{'type':'integer'},'end_line':{'type':'integer'},'replacement':{'type':'string'}},
            'required':['file','start_line','end_line','replacement'],'additionalProperties':False}}},'required':['diagnosis','edits'],'additionalProperties':False}
    def _request(self,endpoint,payload=None):
        if endpoint=='chat/completions' and payload is not None:
            payload={**payload,'response_format':{'type':'json_schema','json_schema':{'name':'project_rtl_patch','strict':True,'schema':self.schema}}}
        return super()._request(endpoint,payload)


def public_messages(project,observations,*,previous=None):
    context={'name':project.config['name'],'dut_top':project.config['dut_top'],'contract':project.config['contract'],
        'dut_parameters':project.config['dut_parameters'],'defines':project.config['defines'],'editable_sources':{},'readonly_design_sources':{},'public_testbenches':{},
        'public_test_configuration':[{k:t[k] for k in ('id','top','parameters','minimum_checks','success_marker')} for t in project.public_tests],
        'public_observations':observations}
    for path,source in project.sources.items():
        if path not in project.config['editable_files'] and len(source.encode())>24000:
            numbered='Readonly dependency: body omitted to bound inference context. Module/package headers: '+json.dumps(interfaces(source)[0])
        else:numbered='\n'.join(f'{i}: {line}' for i,line in enumerate(source.splitlines(),1))
        context['editable_sources' if path in project.config['editable_files'] else 'readonly_design_sources'][path]=numbered
    for test in project.public_tests:
        for path in test['files']+test['include_files']:context['public_testbenches'][path]=project.files[path].decode()
    if previous is not None:context['previous_original_source_proposal']=previous
    serialized=json.dumps(context)
    if len(serialized.encode())>500000:raise ValueError('Repair context exceeds 500 KB. Narrow editable/dependency context before making a paid request.')
    return [{'role':'system','content':'''Repair this user-supplied Verilog/SystemVerilog design using its public testbenches and public execution failures.
You may change only declared editable design files. Return {diagnosis,edits:[{file,start_line,end_line,replacement}]}. Line ranges are inclusive and always refer to ORIGINAL uploaded files. Replacements are complete line blocks. Maximum twelve non-overlapping edits.
Preserve copyright/header, module/package headers, ports, parameter defaults, type declarations, compiler directives and clock/reset event forms. Synthesizable functions/tasks and wide signals are permitted. Fix design logic; never edit tests/configuration, access testbench hierarchy, add simulator control/file tasks, bypass checks, or output a pass marker. No corrected target or private audit source/results are provided.
If a prior proposal is present, use its public failures to reconsider it, while keeping all edits relative to the original files. Diagnosis is a hypothesis, not a correctness guarantee. Return only the requested JSON.'''},
        {'role':'user','content':serialized}]


def propose(project,observations,directory,*,previous=None):
    directory=Path(directory);directory.mkdir()
    messages=public_messages(project,observations,previous=previous);write_json(directory/'messages.json',messages)
    ledger=BudgetLedger();summary=ledger.summary();quote=ledger.quote(MODEL,MAX_TOKENS)
    if quote['reserved_usd']>min(4.,summary['remaining_usd'],summary['phase_remaining_usd']):raise ValueError('Budget cannot reserve one bounded project repair request')
    client=ProjectClient(project.config['editable_files']);client.verify_model();start=time.monotonic()
    write_json(directory/'request_started.json',{'max_requests':1,'automatic_retry':False})
    record={'status':'MODEL_ERROR','api_requests':0,'changes':{}}
    try:
        response=client.generate(messages,max_tokens=MAX_TOKENS);write_json(directory/'response.json',response)
        choice=response['choices'][0]
        if choice.get('finish_reason')!='stop':raise ValueError('Project patch response incomplete')
        proposal=json.loads(choice['message']['content']);record['proposal']=proposal;changes=apply_edits(project,proposal)
        record.update({'status':'VALID_PATCH','proposal':proposal,'changes':changes})
    except Exception as exc:
        record['error']=client.redact(type(exc).__name__+': '+str(exc))
        if (directory/'response.json').exists():record['status']='PATCH_REJECTED'
    record.update({'api_requests':client.inference_requests,'cost':client.last_cost,'wall_seconds':time.monotonic()-start})
    write_json(directory/'proposal.json',record);return record
