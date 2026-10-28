"""Public counterexample-guided repair, followed by terminal private audits."""
from pathlib import Path
import time

from ..common import ROOT,new_run_dir,sha256,write_json
from ..project_repair.project import archive_project
from ..project_repair.checker import check_project
from ..project_repair.agent import propose
from ..project_repair.workflow import public_feedback
from .contract import TEXT,load_contract,bind_contract,contract_id
from .formal import check_properties
from .regressions import (inherited_cases,contract_sequence,public_case,merge_cases,
                          with_bundle,check_bundle,failed_public_feedback)
from .resources import compare as compare_resources


def feedback(smoke,properties,c,regressions=None,cases=None):
    value={'public_testbenches':public_feedback(smoke),'independent_public_contract':TEXT,
           'fifo_configuration':{k:c[k] for k in ('kind','ports','data_width','depth','discovery_steps')},
           'public_property_status':properties['status'],'public_property_steps':properties['steps']}
    if properties.get('replay'):
        value['counterexample_inputs_and_observations']=properties['replay']['observations']
        value['independent_replay_violations']=properties['replay']['violations']
    if regressions is not None:value['public_regressions']=failed_public_feedback(regressions,cases or [])
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
    protocol=ROOT/'docs/PROPERTY_REPAIR_PROTOCOL.md'
    if protocol.exists():(snapshot/'PROTOCOL.md').write_bytes(protocol.read_bytes())
    write_json(root/'controller_hashes.json',{p.name:sha256(p.read_bytes()) for p in snapshot.iterdir() if p.is_file()})
    def finish(status):
        result.update(status=status,wall_seconds=time.monotonic()-start)
        write_json(root/'result.json',result);return result
    try:
        retained=inherited_cases(project,c)
        if retained:
            import json
            previous_export=json.loads(project.files['rtlrefine_regressions/manifest.json'])
            current_hashes={p:sha256(project.files[p]) for p in previous_export['source_hashes']}
            result['previous_export_source_changed']=current_hashes!=previous_export['source_hashes']
    except (ValueError,KeyError,TypeError) as exc:
        result['error']=str(exc);return finish('REGRESSION_SETUP_REQUIRED')
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
    cases=merge_cases(retained,[public_case(properties)],[contract_sequence(c)])
    event('regressions','Generate executable public regressions from the contract and retain any earlier counterexamples')
    try:
        reproduction=with_bundle(project,c,cases)
        regressions=check_bundle(reproduction,root/'original_public_regressions')
    except (ValueError,RuntimeError,OSError) as exc:
        result['error']=str(exc);return finish('REGRESSION_SETUP_REQUIRED')
    result['original_regressions']=regressions
    if regressions['status'] not in {'REGRESSIONS_PASS','REGRESSION_FAILED'}:return finish('REGRESSION_SETUP_REQUIRED')
    discovered=public_case(properties)
    if discovered and any(t['id']==discovered['id'] and t['passed'] for t in regressions['tests']):
        return finish('REGRESSION_ORACLE_MISMATCH')
    if not regressions['accepted']:
        reproduction_blob=archive_project(reproduction);(root/'reproduction-project.zip').write_bytes(reproduction_blob)
        result['reproduction_archive_sha256']=sha256(reproduction_blob)
    selected={};needs_repair=not smoke['accepted'] or properties['status']=='COUNTEREXAMPLE' or not regressions['accepted']
    if needs_repair and not repair:return finish('INDEPENDENT_FAILURE_FOUND')
    interfaces={t['id']:t.get('interface') for t in smoke['tests'] if t.get('interface')}
    if needs_repair:
        observations=feedback(smoke,properties,c,regressions,cases);previous=None;found=False
        for attempt in range(2):
            event('model','Give NVIDIA only the public contract and reproduced failure; attempt '+str(attempt+1))
            try:proposal=propose(project,observations,root/f'proposal_{attempt+1}',previous=previous)
            except (ValueError,RuntimeError,OSError) as exc:
                result['error']=str(exc);return finish('MODEL_SETUP_REQUIRED')
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
            cases=merge_cases(cases,[public_case(formal)])
            try:regression_check=check_bundle(with_bundle(project,c,cases,changes),root/f'candidate_{attempt+1}_regressions')
            except (ValueError,RuntimeError,OSError) as exc:
                entry['regression_error']=str(exc);return finish('CANDIDATE_REGRESSION_UNPROVEN')
            entry['public_regressions']=regression_check
            if regression_check['status'] not in {'REGRESSIONS_PASS','REGRESSION_FAILED'}:return finish('CANDIDATE_REGRESSION_UNPROVEN')
            discovered=public_case(formal)
            if discovered and any(t['id']==discovered['id'] and t['passed'] for t in regression_check['tests']):
                return finish('REGRESSION_ORACLE_MISMATCH')
            if checked['accepted'] and formal['status']=='BOUNDED_PASS' and regression_check['accepted']:
                selected=changes;result['diagnosis']=proposal['proposal']['diagnosis'];found=True;break
            observations=feedback(checked,formal,c,regression_check,cases)
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
    event('export_regressions','Rebuild the exact export and run every retained regression with the standalone runner')
    try:
        exported=with_bundle(project,c,cases,selected)
        portable_check=check_bundle(exported,root/'independent_export_regressions',standalone=True)
    except (ValueError,RuntimeError,OSError) as exc:
        portable_check={'status':'UNPROVEN','accepted':False,'error':str(exc),'tests':[]}
    result['final_regressions']=portable_check
    result['regression_cases']=[{'id':case['id'],'origin':case['origin'],'steps':len(case['inputs'])} for case in cases]
    result['accepted']=final['accepted'] and all(a['status']=='BOUNDED_PASS' for a in audits) and portable_check['accepted']
    if result['accepted']:
        event('resources','Compare mapped logic LUT, register and memory primitives under the same Xilinx 7-series synthesis settings')
        try:
            result['resource_comparison']=compare_resources(project,root/'original_properties/__rtlrefine/frozen/design.v',
                root/f'independent_property_audit_{len(c["audit_steps"])}/__rtlrefine/frozen/design.v',root/'resource_comparison')
        except (ValueError,RuntimeError,OSError,KeyError,TypeError) as exc:
            result['resource_comparison']={'status':'UNAVAILABLE','error':str(exc),'affects_correctness_acceptance':False}
        blob=archive_project(exported);(root/'checked-project.zip').write_bytes(blob)
        result['checked_archive_sha256']=sha256(blob)
        event('complete','The exact project passed tests, bounded properties, progress and the portable regression suite')
        return finish('CHECKED_WITH_PROPERTIES')
    event('rejected','Final audit rejected the selected source; no checked export and no further model request')
    return finish('FINAL_AUDIT_REJECTED')
