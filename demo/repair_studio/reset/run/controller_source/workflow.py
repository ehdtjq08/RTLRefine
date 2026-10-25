"""A failing supported RTL file to an exact, independently rechecked patch."""
from pathlib import Path
import json
import re
import time

from ..common import ROOT,new_run_dir,sha256,write_json
from ..known_bugs_v2.cases import DATA,load,source_policy
from ..known_bugs_v2.engine import run_trace
from ..known_bugs_v2.evaluator import evaluate,feedback
from ..known_bugs_v2.runner import BenchmarkRunner
from ..repair_search.execution import discover
from ..repair_search.candidates import make_pool
from ..evidence_ranking.features import build_cards,heuristic_order,size_order
from ..evidence_ranking.service import rank_existing_pool
from .engine import screen_all
from .agent import diagnose

CASES={
    'overflow':{'case_id':'axis-fifo-d12_d12','title':'Overflowed frame leaks through a packet FIFO',
        'problem':'An oversized frame should be dropped as a whole. A partial frame must not escape the FIFO.'},
    'length':{'case_id':'axis-frame-len-d13_d13','title':'Back-to-back frames get the wrong length',
        'problem':'Report the enabled byte count of each completed frame, including consecutive frames.'},
    'reset':{'case_id':'axis-frame-fifo-d11_d11','title':'Reset leaves stale packet state',
        'problem':'Flush packet pointers and partial-frame/drop state together when reset is asserted.'},
}


def original(key):return (DATA/CASES[key]['case_id']/'input.v').read_text()


def witness(compiled,case,trace,runner,port,cycle):
    result=run_trace(compiled,trace,case['top'],runner,capture=True)
    if not result['passed']:return None
    actual=(compiled/'observed.hex').read_text().splitlines();expected=Path(trace['expected']).read_text().splitlines()
    column=trace['outputs'].index(port);rows=[]
    for i in range(max(0,cycle-4),min(len(actual),cycle+5)):
        a=actual[i].split()[column];e=expected[i].split()[column]
        rows.append({'cycle':i,'expected':e,'actual':a,'match':e=='?' or int(e,16)==int(a,16)})
    return {'port':port,'rows':rows,'sampling':'After current inputs settle, before the rising edge; hexadecimal values; ? is unqualified data'}


def repair(key,source,*,live=False,output=None,on_event=None):
    started=time.monotonic();root=new_run_dir('guided_batch_repair',output);case=load(CASES[key]['case_id']);base=DATA/case['id']
    dependencies=(base/'dependencies.v').read_text();source_policy(source,(base/'input.v').read_text(),case['ports'])
    runner=BenchmarkRunner();events=[]
    def event(stage,message):
        row={'stage':stage,'message':message,'elapsed_seconds':round(time.monotonic()-started,3)}
        events.append(row);write_json(root/'events.json',events)
        if on_event:on_event(row)
    (root/'original.v').write_text(source);write_json(root/'case.json',case)
    write_json(root/'protocol.json',{'key':key,'source_sha256':sha256(source.encode()),'live_model':live,
        'search':'First ranked candidate standalone fast path; then complete public-trace batch screening if needed',
        'selection':'First public-passing candidate in fixed rank order, then unchanged standalone three-profile admission; audit failure is terminal',
        'model_role':'Prioritizes source-generated IDs and may revise using public candidate checks; never authors RTL or sees private audits before selection',
        'max_model_requests':2 if live else 0,
        'engine_hashes':{p.name:sha256(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')}})
    snapshot=root/'controller_source';snapshot.mkdir()
    for p in Path(__file__).parent.glob('*.py'):(snapshot/p.name).write_bytes(p.read_bytes())
    event('reproduce','Reproduce the original failure')
    baseline=discover(case['id'],source,root/'original_discovery');write_json(root/'original_discovery.json',baseline)
    record={'key':key,'case_id':case['id'],'source_sha256':sha256(source.encode()),'accepted':False,'api_requests':0,
            'status':'ORIGINAL_CHECK_FAILED','original_discovery':baseline,'directory':str(root),'scope':case['oracle_scope']}
    if not baseline.get('traces'):
        record['error']=baseline.get('error','Original did not compile');write_json(root/'result.json',record);return record
    if baseline['discovery_pass']:
        record['status']='ORIGINAL_PUBLIC_PROFILE_PASSES';write_json(root/'result.json',record);return record
    trace={**case['traces'][0],'stimulus':str(base/case['traces'][0]['stimulus']),'expected':str(base/case['traces'][0]['expected'])}
    failure=baseline['traces'][0]['first_mismatches'][0]
    record['before']=witness(root/'original_discovery/compiled',case,trace,runner,failure['port'],failure['cycle'])
    event('hypotheses','Build bounded patch hypotheses from the original source')
    prepared=root/'hypotheses';prepared.mkdir();(prepared/'candidate.v').write_text(source);(prepared/'dependencies.v').write_text(dependencies)
    (prepared/'inspect.ys').write_text(f'read_verilog -sv candidate.v dependencies.v\nhierarchy -check -top {case["top"]}\nproc\nwrite_json interface.json\nflatten\nmemory_collect\nwrite_json flattened.json\n')
    command=runner.run('inspect',prepared,case['top'])
    if command['status']!='PASS':raise RuntimeError('Original netlist extraction failed')
    module=json.loads((prepared/'interface.json').read_text())['modules'][case['top']]
    widths={n:len(v['bits']) for n,v in module['netnames'].items() if re.fullmatch(r'[A-Za-z_]\w*',n)}
    pool=[]
    for candidate in make_pool(source,widths):
        try:source_policy(candidate['rtl'],source,case['ports'])
        except ValueError:continue
        pool.append(candidate)
    write_json(root/'pool.json',pool);record['pool_candidates']=len(pool)
    if not pool:
        record['status']='NO_SUPPORTED_PATCHES';write_json(root/'result.json',record);return record
    flattened=json.loads((prepared/'flattened.json').read_text())['modules'][case['top']]
    event('diagnose','Ask NVIDIA Nemotron to explain and prioritize patch hypotheses' if live else 'Prioritize patch hypotheses with circuit evidence; no model request')
    ranked=rank_existing_pool(case,source,dependencies,pool,flattened,feedback(baseline),root/'ranking',live=False)
    if live:
        diagnosis=diagnose(case,source,dependencies,ranked['cards'],feedback(baseline),root/'nvidia_diagnosis')
        record['diagnosis']=diagnosis;record['api_requests']=diagnosis['api_requests']
        if diagnosis['status']=='VALID':ranked['order']=diagnosis['ids']+[i for i in ranked['order'] if i not in diagnosis['ids']]
    record['nvidia_prefix_applied']=bool(record.get('diagnosis',{}).get('status')=='VALID')
    record['ranking']={k:ranked[k] for k in ('order','heuristic_order','source_sha256','scope')}
    by={'patch_'+c['rtl_sha256'][:12]:c for c in pool};order=ranked['order'];record['rank_order']=[by[i]['id'] for i in order]
    first=by[order[0]];event('fast_path','Check the highest-priority patch')
    first_check=discover(case['id'],first['rtl'],root/'first_candidate');selected=first if first_check['discovery_pass'] else None
    record['fast_path_pass']=bool(selected)
    if selected is None:
        event('batch','Screen the remaining '+str(len(pool)-1)+' hypotheses with shared candidate compilation')
        remaining=[c for c in pool if c['id']!=first['id']]
        screened=screen_all(source,dependencies,case,remaining,trace,root/'batch_search',runner=runner)
        record['batch']={k:v for k,v in screened.items() if k!='results'}
        public_passes=[]
        for identity in order[1:]:
            candidate=by[identity]
            if screened['results'][candidate['id']]['passed']:public_passes.append(identity)
        if live and public_passes:
            event('revise','Use public check results to revise the diagnosis and choose a passing hypothesis')
            public_cards=[c for c in ranked['cards'] if c['id'] in public_passes]
            revised=diagnose(case,source,dependencies,public_cards,feedback(baseline),root/'nvidia_revision',tool_feedback={
                'earlier_hypothesis':record.get('diagnosis',{}).get('diagnosis'),
                'first_candidate_failed':first['id'],'first_candidate_observations':feedback(first_check),
                'public_passed_candidates':[by[i]['id'] for i in public_passes],
                'screened_candidates':len(remaining),'private_audits_used':False})
            record['api_requests']+=revised['api_requests'];record['initial_diagnosis']=record.get('diagnosis')
            if revised['status']=='VALID':
                public_passes=revised['ids']+[i for i in public_passes if i not in revised['ids']]
                record['diagnosis']=revised;record['diagnosis_revised_after_public_checks']=True
            else:record['revision_error']=revised
        if public_passes:selected=by[public_passes[0]]
    if selected is None:
        record['status']='NO_PUBLIC_PASS';record['wall_seconds']=time.monotonic()-started;write_json(root/'result.json',record);return record
    event('independent_check','Compile the exact selected patch independently and run all three fixed profiles')
    final=evaluate(case['id'],selected['rtl'],root/'independent_check',runner=runner)
    record.update({'status':final['status'],'accepted':final['accepted'],'selected_id':selected['id'],
        'selected_family':selected['family'],'selected_edits':selected['edits'],'selected_sha256':selected['rtl_sha256'],'final_check':final})
    (root/'selected.v').write_text(selected['rtl'])
    if (root/'independent_check/compiled').exists() and final.get('traces'):
        record['after']=witness(root/'independent_check/compiled',case,trace,runner,failure['port'],failure['cycle'])
    record['wall_seconds']=time.monotonic()-started
    event('complete','Exact patch accepted within the fixed profiles' if final['accepted'] else 'Patch rejected by independent checks')
    write_json(root/'result.json',record);return record
