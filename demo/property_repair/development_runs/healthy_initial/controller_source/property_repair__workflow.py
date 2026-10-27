"""Public counterexample-guided repair, followed by terminal private audits."""
from pathlib import Path
import time

from ..common import new_run_dir,sha256,write_json
from ..project_repair.project import archive_project
from ..project_repair.checker import check_project
from ..project_repair.agent import propose
from ..project_repair.workflow import public_feedback
from .contract import TEXT,load_contract,bind_contract,contract_id
from .formal import check_properties


def feedback(smoke,properties,c):
    value={'public_testbenches':public_feedback(smoke),'independent_public_contract':TEXT,
           'fifo_configuration':{k:c[k] for k in ('kind','ports','data_width','depth','discovery_steps')},
           'public_property_status':properties['status'],'public_property_steps':properties['steps']}
    if properties.get('replay'):
        value['counterexample_inputs_and_observations']=properties['replay']['observations']
        value['independent_replay_violations']=properties['replay']['violations']
    return value


def run_repair(project,*,contract=None,repair=False,output=None,on_event=None):
    c=load_contract(project,contract);project=bind_contract(project,c)
    root=new_run_dir('property_guided_repair',output);start=time.monotonic();events=[]
    def event(stage,text):
        record={'stage':stage,'message':text,'elapsed_seconds':time.monotonic()-start}
        events.append(record);write_json(root/'events.json',events)
        if on_event:on_event(record)
    result={'project_id':project.identity,'contract_id':contract_id(c),'directory':str(root),'accepted':False,'api_requests':0,
            'attempts':[],'mode':'independent_fifo_properties','authored_example_is_accuracy_benchmark':False,
            'scope':'Provided testbenches plus bounded FIFO properties and reachable progress; not unbounded correctness, arbitrary protocols or physical CDC.'}
    (root/'original-project.zip').write_bytes(archive_project(project));write_json(root/'contract.json',c)
    snapshot=root/'controller_source';snapshot.mkdir()
    for directory in (Path(__file__).parent,Path(__file__).parent.parent/'project_repair'):
        for p in directory.glob('*.py'):(snapshot/(directory.name+'__'+p.name)).write_bytes(p.read_bytes())
    def finish(status):
        result.update(status=status,wall_seconds=time.monotonic()-start)
        write_json(root/'result.json',result);return result
    event('smoke','Run the existing public testbench before inspecting independent properties')
    smoke=check_project(project,{},root/'original_smoke',phase='public');result['original_smoke']=smoke
    if any(t['status'] not in {'PASS','ASSERTION_FAILED'} for t in smoke['tests']):
        return finish('PUBLIC_TEST_SETUP_REQUIRED')
    event('discovery','Search the fixed independent FIFO contract, then minimize and replay any counterexample')
    try:properties=check_properties(project,{},c,root/'original_properties',minimize=True)
    except (ValueError,RuntimeError,OSError) as exc:
        result['error']=str(exc);return finish('PROPERTY_SETUP_REQUIRED')
    result['original_properties']=properties
    if properties['status'] not in {'BOUNDED_PASS','COUNTEREXAMPLE'}:return finish(properties['status'])
    selected={};needs_repair=not smoke['accepted'] or properties['status']=='COUNTEREXAMPLE'
    if needs_repair and not repair:return finish('INDEPENDENT_FAILURE_FOUND')
    interfaces={t['id']:t.get('interface') for t in smoke['tests'] if t.get('interface')}
    if needs_repair:
        observations=feedback(smoke,properties,c);previous=None;found=False
        for attempt in range(2):
            event('model','Give NVIDIA only the public contract and reproduced failure; attempt '+str(attempt+1))
            proposal=propose(project,observations,root/f'proposal_{attempt+1}',previous=previous)
            result['api_requests']+=proposal['api_requests'];entry={'number':attempt+1,**proposal};result['attempts'].append(entry)
            if proposal['status']!='VALID_PATCH':
                if proposal['status']!='PATCH_REJECTED' or not proposal['api_requests']:break
                observations={**observations,'patch_rejected':proposal.get('error')};previous=proposal.get('proposal');continue
            changes=proposal['changes'];previous=proposal['proposal']
            event('public_recheck','Rebuild the proposed source and rerun public tests and the public property bound')
            checked=check_project(project,changes,root/f'candidate_{attempt+1}_smoke',phase='public',interfaces=interfaces)
            try:formal=check_properties(project,changes,c,root/f'candidate_{attempt+1}_properties',minimize=True)
            except (ValueError,RuntimeError,OSError) as exc:
                entry['property_error']=str(exc);observations={**observations,'patch_rejected':str(exc)};continue
            entry.update(public_smoke=checked,public_properties=formal)
            if formal['status'] not in {'BOUNDED_PASS','COUNTEREXAMPLE'}:return finish('CANDIDATE_UNPROVEN')
            if checked['accepted'] and formal['status']=='BOUNDED_PASS':
                selected=changes;result['diagnosis']=proposal['proposal']['diagnosis'];found=True;break
            observations=feedback(checked,formal,c)
        if not found:return finish('NO_PUBLIC_PASS')
    # Selection is now immutable. No audit result can select another candidate.
    result['changes']=selected;result['selection_frozen']=True
    write_json(root/'selection.json',{'design_hashes':{p:sha256(selected.get(p,v).encode()) for p,v in project.sources.items()},'contract_id':contract_id(c)})
    event('final_tests','Independently rebuild the selected files and run every supplied testbench, including audits')
    final=check_project(project,selected,root/'independent_final_tests',phase='all',interfaces=interfaces);result['final_tests']=final
    event('final_properties','Check the fixed deeper bounds and require reachable full, stalled, overlapping, wrapped and reset activity')
    audits=[]
    for i,bound in enumerate(c['audit_steps']):
        try:checked=check_properties(project,selected,c,root/f'independent_property_audit_{i+1}',steps=bound,require_progress=i==len(c['audit_steps'])-1)
        except (ValueError,RuntimeError,OSError) as exc:
            checked={'status':'UNPROVEN','steps':bound,'error':str(exc)}
        audits.append(checked)
    result['property_audits']=audits
    result['accepted']=final['accepted'] and all(a['status']=='BOUNDED_PASS' for a in audits)
    if result['accepted']:
        blob=archive_project(project,selected);(root/'checked-project.zip').write_bytes(blob)
        result['checked_archive_sha256']=sha256(blob)
        event('complete','The exact project passed supplied tests, deeper bounded properties and progress reachability')
        return finish('CHECKED_WITH_PROPERTIES')
    event('rejected','Final audit rejected the selected source; no checked export and no further model request')
    return finish('FINAL_AUDIT_REJECTED')
