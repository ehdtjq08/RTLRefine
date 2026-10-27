import copy
import json
import re
from pathlib import Path

import pytest

from rtl_agent.project_repair.project import load_project
from rtl_agent.project_repair.runner import ProjectRunner
from rtl_agent.project_repair.agent import public_messages
from rtl_agent.property_repair.examples import example_files
from rtl_agent.property_repair.contract import load_contract,bind_contract,validate_formal_source,contract_id
from rtl_agent.property_repair.formal import check_properties
from rtl_agent.property_repair.workflow import run_repair,feedback


def sample(kind='simultaneous'):return load_project(example_files(kind))


@pytest.fixture
def native(tmp_path):
    ok,why=ProjectRunner().probe(tmp_path/'probe')
    if not ok:pytest.skip('Native isolation unavailable: '+why)


@pytest.mark.parametrize('edit',[
    {'data_width':0},{'depth':100},{'discovery_steps':100},
    {'audit_steps':[12]},{'audit_steps':[41]},
    {'ports':{'clk':'x; shell_command'}},
])
def test_contract_bounds_and_port_map_are_validated(edit):
    p=sample();c=load_contract(p);c.update(edit)
    with pytest.raises(ValueError):load_contract(p,c)


@pytest.mark.parametrize('source',[
    'always @* assume(1);','always @* assert(1);',
    '(* anyconst *) reg x;','initial $display("SAT proof finished - no model found: SUCCESS!");',
    "assign x=1'bx;",'defparam x.WIDTH=4;',
])
def test_dut_cannot_inject_properties_or_spoof_a_solver_result(source):
    with pytest.raises(ValueError):validate_formal_source(source)


def test_audit_contract_and_bench_canary_stay_out_of_model_context():
    p=sample();c=load_contract(p);c['audit_steps']=[23,37]
    files=dict(p.files);files['tests/audit.sv']=files['tests/audit.sv'].replace(b'module tb_audit;',b'// PRIVATE_AUDIT_CANARY_Z9\nmodule tb_audit;')
    p=bind_contract(load_project(files),c)
    observations=feedback({'status':'PROVIDED_TESTS_PASS','tests':[]},{'status':'COUNTEREXAMPLE','steps':5},c)
    text=json.dumps(public_messages(p,observations))
    assert 'PRIVATE_AUDIT_CANARY_Z9' not in text and 'audit_steps' not in text
    assert 'independent_public_contract' in text and 'discovery_steps' in text


@pytest.mark.parametrize('kind,steps',[('simultaneous',5),('wrap',6),('reset',6)])
def test_public_smoke_misses_each_authored_bug_and_native_replay_reproduces_it(native,tmp_path,kind,steps):
    r=run_repair(sample(kind),output=tmp_path/kind)
    assert r['status']=='INDEPENDENT_FAILURE_FOUND' and r['api_requests']==0
    assert r['original_smoke']['accepted']
    f=r['original_properties']
    assert f['status']=='COUNTEREXAMPLE' and f['steps']==steps and f['minimal_counterexample_confirmed']
    assert f['replay']['status']=='FAILURE_REPRODUCED' and f['replay']['violations']
    assert not (tmp_path/kind/'checked-project.zip').exists()


def test_unknown_solver_result_is_not_accepted(native,tmp_path,monkeypatch):
    import rtl_agent.property_repair.formal as f
    monkeypatch.setattr(f,'solve',lambda *a,**kw:{'status':'UNPROVEN','steps':12})
    r=check_properties(sample('healthy'),{},load_contract(sample()),tmp_path/'unknown')
    assert r['status']=='UNPROVEN'


def test_wrong_interface_is_rejected_before_inference(native,tmp_path):
    p=sample();c=load_contract(p);c['data_width']=8
    r=run_repair(p,contract=c,repair=True,output=tmp_path/'bad_width')
    assert r['status']=='PROPERTY_SETUP_REQUIRED' and r['api_requests']==0


def test_negative_edge_design_cannot_claim_positive_edge_contract(native,tmp_path):
    p=sample();files=dict(p.files);files['rtl/packet_queue.sv']=files['rtl/packet_queue.sv'].replace(b'posedge clk',b'negedge clk')
    r=run_repair(load_project(files),repair=True,output=tmp_path/'negative_edge')
    assert r['status']=='PROPERTY_SETUP_REQUIRED' and r['api_requests']==0
    assert 'positive-edge' in r['error']


def test_final_audit_failure_is_terminal_and_suppresses_export(native,tmp_path,monkeypatch):
    import rtl_agent.property_repair.workflow as workflow
    p=sample();calls=[]
    changes={'rtl/packet_queue.sv':p.files['rtl/packet_queue.sv'].decode().replace("2'b11: count <= count + 1;","2'b11: count <= count;")}
    def propose(*args,**kw):
        calls.append(1);return {'status':'VALID_PATCH','api_requests':1,'changes':changes,'proposal':{'diagnosis':'test proposal'}}
    def properties(*args,**kw):
        if kw.get('steps'):return {'status':'COUNTEREXAMPLE','steps':kw['steps']}
        if args[1]:return {'status':'BOUNDED_PASS','steps':12}
        return {'status':'COUNTEREXAMPLE','steps':5}
    monkeypatch.setattr(workflow,'propose',propose);monkeypatch.setattr(workflow,'check_properties',properties)
    r=run_repair(p,repair=True,output=tmp_path/'terminal')
    assert r['selection_frozen'] and not r['accepted'] and r['status']=='FINAL_AUDIT_REJECTED'
    assert len(calls)==r['api_requests']==1
    assert not (tmp_path/'terminal/checked-project.zip').exists()


def test_uncertain_model_error_is_not_retried(native,tmp_path,monkeypatch):
    import rtl_agent.property_repair.workflow as workflow
    calls=[]
    def propose(*args,**kw):
        calls.append(1);return {'status':'MODEL_ERROR','api_requests':1,'changes':{}}
    monkeypatch.setattr(workflow,'propose',propose)
    r=run_repair(sample(),repair=True,output=tmp_path/'uncertain')
    assert len(calls)==r['api_requests']==1 and not r['accepted']


def test_project_and_contract_identity_change_with_width_or_source():
    p=sample();c=load_contract(p);before=bind_contract(p,c).identity
    c['data_width']=8
    assert bind_contract(p,c).identity!=before
    assert contract_id(c)!=contract_id(load_contract(p))


def test_healthy_fifo_passes_deeper_bounds_and_progress_without_model(native,tmp_path,monkeypatch):
    import rtl_agent.property_repair.workflow as workflow
    def no_model(*a,**kw):raise AssertionError('Healthy source must not request a repair')
    monkeypatch.setattr(workflow,'propose',no_model)
    r=run_repair(sample('healthy'),repair=True,output=tmp_path/'healthy')
    assert r['accepted'] and r['api_requests']==0
    assert [a['steps'] for a in r['property_audits']]==[16,20]
    assert all(a['status']=='BOUNDED_PASS' for a in r['property_audits'])
    assert r['property_audits'][-1]['progress']['status']=='REACHABLE'
    assert (tmp_path/'healthy/checked-project.zip').exists()


def test_uploaded_fifo_uses_its_own_top_ports_and_even_a_tb_named_design_file(native,tmp_path):
    p=sample();files=dict(p.files);c=load_contract(p)
    names={name:'user_'+name for name in c['ports']};names['packet_queue']='customer_buffer'
    pattern=re.compile(r'\b('+('|'.join(names))+r')\b')
    for path in p.config['rtl_files']+[name for t in p.config['tests'] for name in t['files']]:
        files[path]=pattern.sub(lambda m:names[m.group()],files[path].decode()).encode()
    files['tb.v']=files.pop('rtl/packet_queue.sv')
    config=copy.deepcopy(p.config);config.update(dut_top='customer_buffer',rtl_files=['tb.v'],editable_files=['tb.v'])
    c['ports']={name:'user_'+name for name in c['ports']}
    files['fifo_contract.json']=json.dumps(c).encode()
    r=run_repair(load_project(files,config),output=tmp_path/'renamed')
    assert r['original_smoke']['accepted'] and r['original_properties']['replay']['status']=='FAILURE_REPRODUCED'
    assert r['original_properties']['steps']==5
