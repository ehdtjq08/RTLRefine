"""Template-independent project checking and a maximum two-request repair loop."""
import json
from pathlib import Path
import time

from ..common import new_run_dir,sha256,write_json
from .checker import check_project
from .project import archive_project
from .agent import propose


def public_feedback(result):
    return {'status':result['status'],'tests':[{k:t[k] for k in ('id','status','checks','log_tail','error') if k in t}
        for t in result.get('tests',[]) if t['phase']=='public']}


def run_project(project,*,repair=False,output=None,on_event=None):
    start=time.monotonic();root=new_run_dir('user_project_repair',output);events=[]
    def event(stage,message):
        e={'stage':stage,'message':message,'elapsed_seconds':time.monotonic()-start};events.append(e);write_json(root/'events.json',events)
        if on_event:on_event(e)
    (root/'original-project.zip').write_bytes(archive_project(project));write_json(root/'project.json',project.config)
    snapshot=root/'controller_source';snapshot.mkdir()
    for p in Path(__file__).parent.glob('*.py'):(snapshot/p.name).write_bytes(p.read_bytes())
    result={'project_id':project.identity,'project_name':project.config['name'],'accepted':False,'api_requests':0,'attempts':[],
        'directory':str(root),'mode':'user_testbench_project','batch_speed_claim_applies':False,
        'scope':'Passes only the provided immutable self-checking testbenches; no arbitrary-design completeness, synthesis-timing or physical CDC guarantee'}
    event('public_check','Compile the submitted design and run public testbenches')
    baseline=check_project(project,{},root/'original_public',phase='public');result['baseline']=baseline
    interfaces={t['id']:t.get('interface') for t in baseline['tests'] if t.get('interface')}
    selected={}
    if not baseline['accepted'] and repair:
        unsupported={'PREPROCESS_FAILED','UNSUPPORTED_DUT','TEST_COMPILE_FAILED','INVALID_TEST','TOOL_UNAVAILABLE','INCONCLUSIVE','WORKER_MUTATED_INPUT'}
        if any(t['status'] in unsupported for t in baseline['tests']):
            result.update(status='PROJECT_SETUP_REQUIRED',error='Resolve source/dependency, testbench protocol or tool setup before paid diagnosis.')
            write_json(root/'result.json',result);return result
        prior=None;observations=public_feedback(baseline)
        for attempt in range(2):
            event('model_patch','Ask NVIDIA for a design-only multi-file patch, attempt '+str(attempt+1))
            proposal=propose(project,observations,root/f'proposal_{attempt+1}',previous=prior)
            result['api_requests']+=proposal['api_requests'];entry={'number':attempt+1,**proposal};result['attempts'].append(entry)
            if proposal['status']!='VALID_PATCH':
                if proposal['status']!='PATCH_REJECTED' or not proposal['api_requests']:break
                observations={'status':'PATCH_REJECTED','error':proposal.get('error')};prior=proposal.get('proposal');continue
            event('public_candidate','Compile the exact patch and run public tests; private tests stay hidden')
            checked=check_project(project,proposal['changes'],root/f'candidate_{attempt+1}_public',phase='public',interfaces=interfaces)
            entry['public_check']=checked
            if checked['accepted']:
                selected=proposal['changes'];result['diagnosis']=proposal['proposal']['diagnosis'];break
            observations=public_feedback(checked);prior=proposal['proposal']
        else:selected={}
        if not selected:
            result.update(status='NO_PUBLIC_PASS',wall_seconds=time.monotonic()-start);write_json(root/'result.json',result);return result
    elif not baseline['accepted']:
        result.update(status='PUBLIC_TESTS_FAILED',wall_seconds=time.monotonic()-start);write_json(root/'result.json',result);return result
    event('final_check','Rebuild selected uninstrumented files independently and run every provided testbench')
    final=check_project(project,selected,root/'independent_final',phase='all',interfaces=interfaces)
    result.update({'status':final['status'],'accepted':final['accepted'],'final_check':final,'changes':selected,
        'selected_design_hashes':final['design_hashes'],'wall_seconds':time.monotonic()-start,
        'public_tests':len(project.public_tests),'audit_tests':len(project.audit_tests)})
    if final['accepted']:
        (root/'checked-project.zip').write_bytes(archive_project(project,selected))
        result['checked_archive_sha256']=sha256((root/'checked-project.zip').read_bytes())
    event('complete','All provided tests passed' if final['accepted'] else 'Final verification rejected this source; no further candidate is selected')
    write_json(root/'result.json',result);return result
