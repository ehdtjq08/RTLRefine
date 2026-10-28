import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from rtl_agent.project_repair.project import load_project,read_archive,archive_project
from rtl_agent.project_repair.runner import ProjectRunner
from rtl_agent.project_repair.workflow import run_project
from rtl_agent.property_repair.examples import example_files
from rtl_agent.property_repair.contract import load_contract,bind_contract
from rtl_agent.property_repair.regressions import (with_bundle,check_bundle,public_case,contract_sequence,
                                                  inherited_cases,merge_cases,FOLDER)
from rtl_agent.property_repair.portable import expected_trace,run_suite
from rtl_agent.property_repair.workflow import run_repair


@pytest.fixture
def native(tmp_path):
    ok,why=ProjectRunner().probe(tmp_path/'probe')
    if not ok:pytest.skip('Native isolation unavailable: '+why)


def project():
    p=load_project(example_files());return bind_contract(p,load_contract(p))


def cases(p):
    # Public minimal input sequence, not expected outputs from a broken DUT.
    rows=[{'rst':1,'s_valid':0,'s_data':0,'m_ready':0},
          {'rst':0,'s_valid':1,'s_data':3,'m_ready':1},
          {'rst':0,'s_valid':1,'s_data':2,'m_ready':1},
          {'rst':0,'s_valid':0,'s_data':0,'m_ready':1},
          {'rst':0,'s_valid':0,'s_data':0,'m_ready':0}]
    f={'status':'COUNTEREXAMPLE','witness':rows,'replay':{'status':'FAILURE_REPRODUCED'}}
    return [public_case(f),contract_sequence(load_contract(p))]


def fixed(p):return {'rtl/packet_queue.sv':p.files['rtl/packet_queue.sv'].decode().replace("2'b11: count <= count + 1;","2'b11: count <= count;")}


def extract(p,path):
    path.mkdir()
    for name,data in read_archive(archive_project(p)).items():
        target=path/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    return path


def execute(root):
    # -I must ignore project-local json.py and any PYTHONPATH injection.
    return subprocess.run([sys.executable,'-I',str(root/FOLDER/'run.py'),'--report',str(root/'fresh-report.json')],
                          cwd=root,env={'PATH':os.environ['PATH'],'PYTHONPATH':str(root)},capture_output=True,text=True,timeout=60)


def test_expected_values_follow_the_contract_not_bad_handshakes():
    rows=[{'rst':1,'s_valid':0,'s_data':0,'m_ready':0}]
    rows += [{'rst':0,'s_valid':1,'s_data':i,'m_ready':0} for i in range(4)]
    rows += [{'rst':0,'s_valid':0,'s_data':0,'m_ready':1} for _ in range(4)]
    trace=expected_trace(rows,4,2)
    assert [r['expected_ready'] for r in trace[1:5]]==[1,1,0,0]
    assert [r['expected_data'] for r in trace[5:7]]==[0,1]
    assert all(r['expected_occupancy']<=2 for r in trace)


def test_zero_cases_and_invalid_stimulus_are_rejected():
    with pytest.raises(ValueError):expected_trace([],4,4)
    with pytest.raises(ValueError):expected_trace([{'rst':1,'s_valid':0,'s_data':16,'m_ready':0}],4,4)
    with pytest.raises(ValueError):expected_trace([{'rst':0,'s_valid':0,'s_data':0,'m_ready':0}],4,4)


def test_generated_tests_fail_original_and_pass_exact_patch(native,tmp_path):
    p=project();c=load_contract(p)
    bad=check_bundle(with_bundle(p,c,cases(p)),tmp_path/'original')
    good=check_bundle(with_bundle(p,c,cases(p),fixed(p)),tmp_path/'fixed')
    assert bad['status']=='REGRESSION_FAILED' and not bad['accepted']
    assert all(not t['passed'] for t in bad['tests'])
    assert good['accepted'] and len(good['tests'])==2
    assert all(t['passed'] for t in good['tests'])


def test_standalone_runner_has_no_app_dependency_and_catches_reintroduced_bug(native,tmp_path):
    p=project();bundle=with_bundle(p,load_contract(p),cases(p),fixed(p));root=extract(bundle,tmp_path/'download')
    (root/'json.py').write_text('raise RuntimeError("project module must never be imported")\n')
    result=execute(root);assert result.returncode==0,result.stdout+result.stderr
    report=json.loads((root/'fresh-report.json').read_text());assert report['accepted'] and report['new_model_calls']==0
    (root/'rtl/packet_queue.sv').write_bytes(p.files['rtl/packet_queue.sv'])
    result=execute(root);assert result.returncode==1,result.stdout+result.stderr
    report=json.loads((root/'fresh-report.json').read_text())
    assert report['source_changed'] and not report['accepted']
    assert all(not t['passed'] for t in report['tests'])


@pytest.mark.parametrize('which',['bench','runner','contract','manifest'])
def test_changed_checker_or_configuration_is_not_a_pass(native,tmp_path,which):
    p=project();root=extract(with_bundle(p,load_contract(p),cases(p),fixed(p)),tmp_path/which)
    if which=='bench':
        f=next((root/FOLDER).glob('*.sv'));f.write_text(f.read_text().replace('$fatal','$display'))
    elif which=='runner':
        with (root/FOLDER/'run.py').open('a') as f:f.write('\n# accidental modification\n')
    elif which=='contract':
        f=root/'fifo_contract.json';c=json.loads(f.read_text());c['depth']=2;f.write_text(json.dumps(c))
    else:
        f=root/FOLDER/'manifest.json';m=json.loads(f.read_text());m['cases']=[];f.write_text(json.dumps(m))
    result=run_suite(root)
    assert not result['accepted'] and result['status']==('CONFIGURATION_CHANGED' if which=='contract' else 'INTEGRITY_ERROR')


def test_regressions_are_preserved_and_deduplicated_on_reimport():
    p=project();c=load_contract(p);first=with_bundle(p,c,cases(p),fixed(p))
    imported=load_project(read_archive(archive_project(first)))
    retained=inherited_cases(imported,c)
    second=with_bundle(imported,c,merge_cases(retained,cases(p),[contract_sequence(c)]))
    again=json.loads(second.files[FOLDER+'/manifest.json'])
    assert len(again['cases'])==2
    assert {v['id'] for v in again['cases']}=={v['id'] for v in cases(p)}
    assert all(second.files[f]==p.files[f] for f in ['tests/smoke.sv','tests/audit.sv'])


def test_generated_namespace_does_not_overwrite_user_assets():
    p=project();files={**p.files,FOLDER+'/user-notes.txt':b'keep me'}
    with pytest.raises(ValueError,match='reserved'):inherited_cases(load_project(files),load_contract(p))


def test_general_project_route_cannot_skip_exported_regressions(native,tmp_path):
    p=project();config=copy.deepcopy(p.config);config['tests']=[p.config['tests'][0]]
    p=load_project(p.files,config)
    exported=with_bundle(p,load_contract(p),cases(p),fixed(p))
    files=dict(exported.files);files['rtl/packet_queue.sv']=p.files['rtl/packet_queue.sv']
    imported=load_project(read_archive(archive_project(load_project(files,config))))
    r=run_project(imported,output=tmp_path/'general')
    assert r['mode']=='independent_fifo_properties' and r['original_smoke']['accepted']
    assert not r['accepted'] and r['api_requests']==0
    assert not r['original_regressions']['accepted']


def test_final_regression_failure_blocks_export_without_another_model_call(native,tmp_path,monkeypatch):
    import rtl_agent.property_repair.workflow as w
    original=w.check_bundle;calls=[];p=project()
    def propose(*a,**kw):
        calls.append(1);return {'status':'VALID_PATCH','api_requests':1,'changes':fixed(p),'proposal':{'diagnosis':'unit test proposal'}}
    def check(bundle,directory,**kwargs):
        result=original(bundle,directory,**kwargs)
        if Path(directory).name=='independent_export_regressions':result.update(accepted=False,status='REGRESSION_FAILED')
        return result
    monkeypatch.setattr(w,'propose',propose);monkeypatch.setattr(w,'check_bundle',check)
    r=run_repair(p,repair=True,output=tmp_path/'gate')
    assert r['selection_frozen'] and r['final_tests']['accepted']
    assert all(a['status']=='BOUNDED_PASS' for a in r['property_audits'])
    assert not r['accepted'] and r['status']=='FINAL_AUDIT_REJECTED' and len(calls)==1
    assert not (tmp_path/'gate/checked-project.zip').exists()


def test_cli_returns_nonzero_for_a_rejected_source(native,tmp_path):
    p=project();z=tmp_path/'bad.zip';z.write_bytes(archive_project(p))
    root=Path(__file__).resolve().parent.parent
    result=subprocess.run([sys.executable,'-m','rtl_agent.property_repair','check','--project',str(z),'--output',str(tmp_path/'cli')],cwd=root,capture_output=True,text=True,timeout=60)
    assert result.returncode==1,result.stdout+result.stderr
    assert 'INDEPENDENT_FAILURE_FOUND' in result.stdout


def test_portable_checks_detect_wrong_clock_edge(native,tmp_path):
    p=project();bundle=with_bundle(p,load_contract(p),cases(p),fixed(p))
    root=extract(bundle,tmp_path/'negative_edge')
    f=root/'rtl/packet_queue.sv';f.write_text(f.read_text().replace('posedge clk','negedge clk'))
    r=run_suite(root)
    assert not r['accepted'] and r['status']=='REGRESSION_FAILED'
    assert 'post-edge' in r['tests'][0]['simulation']['log_tail']


def test_portable_timeout_is_unproven_not_a_claimed_counterexample(native,tmp_path,monkeypatch):
    import rtl_agent.property_repair.portable as portable
    p=project();root=extract(with_bundle(p,load_contract(p),cases(p),fixed(p)),tmp_path/'timeout')
    original=portable.Native.run
    def timeout(self,label,tool,args,**kw):
        if tool=='vvp':return {'status':'TIMEOUT','log_tail':'simulator time limit reached','stage':label}
        return original(self,label,tool,args,**kw)
    monkeypatch.setattr(portable.Native,'run',timeout)
    r=run_suite(root)
    assert not r['accepted'] and r['status']=='REGRESSION_UNPROVEN'


def test_port_inspection_uses_actual_elaborated_widths(native,tmp_path):
    from rtl_agent.property_repair.inspect import inspect_ports
    p=project();cfg=copy.deepcopy(p.config);cfg['dut_parameters']['WIDTH']='8'
    r=inspect_ports(load_project(p.files,cfg),output=tmp_path/'ports')
    assert r['new_model_calls']==0
    assert {v['width'] for v in r['ports'] if v['name'] in {'s_data','m_data'}}=={8}


def test_mapped_resource_report_fingerprints_both_actual_sources(native,tmp_path):
    from rtl_agent.property_repair.resources import compare
    from rtl_agent.common import sha256
    p=project();original=p.files['rtl/packet_queue.sv'];selected=fixed(p)['rtl/packet_queue.sv'].encode()
    before=tmp_path/'before.v';after=tmp_path/'after.v';before.write_bytes(original);after.write_bytes(selected)
    r=compare(p,before,after,tmp_path/'mapping')
    assert r['status']=='AVAILABLE'
    assert r['before']['expanded_source_sha256']==sha256(original)
    assert r['after']['expanded_source_sha256']==sha256(selected)
    assert r['before']['counts']['logic_lut_cells']>0 and r['after']['counts']['flip_flop_cells']>0
    assert not r['affects_correctness_acceptance'] and not r['after']['board_executed']


def test_uploaded_python_is_never_executed_even_with_a_forged_self_hash(tmp_path,monkeypatch):
    import rtl_agent.property_repair.regressions as regressions
    from rtl_agent.common import sha256
    p=project();good=with_bundle(p,load_contract(p),cases(p),fixed(p));files=dict(good.files)
    files[FOLDER+'/run.py']=b'raise RuntimeError("uploaded Python must never execute")\n'
    m=json.loads(files[FOLDER+'/manifest.json']);m['runner_sha256']=sha256(files[FOLDER+'/run.py'])
    files[FOLDER+'/manifest.json']=json.dumps(m).encode()
    def never(*a,**kw):raise AssertionError('Must reject before invoking Python')
    monkeypatch.setattr(regressions.subprocess,'run',never)
    with pytest.raises(ValueError,match='canonical'):
        check_bundle(load_project(files,p.config),tmp_path/'unsafe',standalone=True)


def test_model_catalog_or_setup_error_is_recorded_without_retry(native,tmp_path,monkeypatch):
    import rtl_agent.property_repair.workflow as w
    calls=[]
    def setup_error(*a,**kw):calls.append(1);raise RuntimeError('catalog temporarily unavailable')
    monkeypatch.setattr(w,'propose',setup_error)
    r=run_repair(project(),repair=True,output=tmp_path/'model_setup')
    assert r['status']=='MODEL_SETUP_REQUIRED' and r['api_requests']==0 and len(calls)==1
    assert (tmp_path/'model_setup/result.json').exists()
    assert (tmp_path/'model_setup/reproduction-project.zip').exists()


def test_second_proposal_receives_real_compiler_diagnostics(native,tmp_path,monkeypatch):
    import rtl_agent.property_repair.workflow as w
    p=project();observed=[]
    bad={'rtl/packet_queue.sv':p.files['rtl/packet_queue.sv'].decode()+'\nendmodule\n'}
    def propose(project,observations,*args,**kwargs):
        observed.append(copy.deepcopy(observations))
        changes=bad if len(observed)==1 else fixed(p)
        return {'status':'VALID_PATCH','api_requests':1,'changes':changes,'proposal':{'diagnosis':'test compiler revision'}}
    monkeypatch.setattr(w,'propose',propose)
    r=run_repair(p,repair=True,output=tmp_path/'compiler_revision')
    assert len(observed)==r['api_requests']==2 and r['accepted']
    text=json.dumps(observed[1]).lower()
    assert 'syntax error' in text and 'not_run_because_proposal_did_not_compile' in text
    assert 'audit_steps' not in text and 'tb_audit' not in text
    assert 'public_smoke' in r['attempts'][0]
