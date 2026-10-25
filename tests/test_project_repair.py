import copy
import io
import json
from pathlib import Path
import stat
import zipfile

import pytest

from rtl_agent.project_repair.project import read_archive,load_project,archive_project
from rtl_agent.project_repair.examples import example_files,example_zip
from rtl_agent.project_repair.policy import apply_edits,validate_patch,validate_design
from rtl_agent.project_repair.agent import public_messages
from rtl_agent.project_repair.checker import check_project
from rtl_agent.project_repair.runner import ProjectRunner
from rtl_agent.project_repair.workflow import run_project


def project(kind='wide_math'):return load_project(example_files(kind))


def fixed(p):
    file=p.config['editable_files'][0];old=p.files[file].decode()
    return {file:old.replace('lhs - rhs','lhs + rhs').replace('count_b + 2','count_b + 1')}


def repack(files):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:
        for name,value in files.items():z.writestr(name,value)
    return b.getvalue()


@pytest.mark.parametrize('name',['../escape.sv','/tmp/escape.sv','a/../../b.sv','C:/evil.sv','.env','keys/.env.local'])
def test_zip_paths_and_credentials_are_rejected(name):
    with pytest.raises(ValueError):read_archive(repack({name:b'module x;endmodule'}))


def test_zip_duplicate_and_symlink_entries_are_rejected():
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:
        info=zipfile.ZipInfo('link.sv');info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,'/etc/passwd')
    with pytest.raises(ValueError,match='symlink'):read_archive(b.getvalue())


def test_import_handles_enclosing_directory_and_preserves_license_assets():
    files=example_files();files['LICENSE']=b'MIT original notice';files['README.md']=b'Project setup'
    p=load_project(read_archive(repack({'upload/'+k:v for k,v in files.items()})))
    exported=read_archive(archive_project(p))
    assert exported['LICENSE']==files['LICENSE'] and exported['README.md']==files['README.md']
    assert p.config['dut_top']=='customer_top'


def test_testbench_cannot_be_marked_editable():
    files=example_files();config=json.loads(files['rtlrefine.json']);config['editable_files']=['tests/public.sv']
    with pytest.raises(ValueError,match='editable'):load_project(files,config)


def test_plain_exit_without_completion_contract_is_not_importable():
    files=example_files();files['tests/public.sv']=files['tests/public.sv'].replace(b'`RTLREFINE_DONE(checks);',b'$finish;')
    with pytest.raises(ValueError,match='success_marker'):load_project(files)


def test_model_patch_changes_real_logic_outside_old_fixed_edit_families():
    p=project();path='rtl/word_math.sv';lines=p.files[path].decode().splitlines();line=next(i+1 for i,t in enumerate(lines) if 'lhs - rhs' in t)
    result=apply_edits(p,{'diagnosis':'Arithmetic operation differs from public contract','edits':[{'file':path,'start_line':line,'end_line':line,'replacement':'    combine = lhs + rhs;'}]})
    assert 'combine = lhs + rhs;' in result[path]
    with pytest.raises(ValueError):apply_edits(p,{'diagnosis':'edit tests','edits':[{'file':'tests/public.sv','start_line':1,'end_line':1,'replacement':'// bypass'}]})


def test_ports_and_parameters_stay_fixed_but_synthesizable_functions_are_allowed():
    p=project();validate_patch(p,fixed(p));validate_design(p.files['rtl/word_math.sv'].decode())
    with pytest.raises(ValueError,match='interfaces'):validate_patch(p,{'rtl/word_math.sv':p.files['rtl/word_math.sv'].decode().replace('WIDTH = 129','WIDTH = 64')})


def test_audit_source_and_data_never_enter_model_context():
    files=example_files();files['tests/audit.sv']+=b'\n// PRIVATE_AUDIT_CANARY_88\n'
    p=load_project(files);text=json.dumps(public_messages(p,{'status':'PUBLIC_TESTS_FAILED'}))
    assert 'PRIVATE_AUDIT_CANARY_88' not in text and 'tb_audit' not in text
    assert 'tb_public' in text and '129' in text


@pytest.mark.parametrize('source',['module x; initial $system("id"); endmodule','module x; initial $finish; endmodule',
    'module x; initial $fopen("/etc/passwd"); endmodule','module x; initial tb_public.emit(); endmodule'])
def test_dut_cannot_execute_file_or_checker_tasks(source):
    with pytest.raises(ValueError):validate_design(source,test_tops=['tb_public'])


@pytest.fixture
def native(tmp_path):
    runner=ProjectRunner();ok,why=runner.probe(tmp_path/'probe')
    if not ok:pytest.skip(why)
    return runner


def test_wide_multifile_function_project_uses_its_own_oracle(tmp_path,native):
    p=project();bad=check_project(p,{},tmp_path/'bad',runner=native)
    assert not bad['accepted'] and bad['tests'][0]['status']=='ASSERTION_FAILED'
    good=check_project(p,fixed(p),tmp_path/'good',runner=native)
    assert good['accepted'] and [t['checks'] for t in good['tests']]==[2,40]
    ports=good['tests'][0]['interface'][0]['ports']
    assert ports and all(port['width']==129 for port in ports)


def test_multiple_clocks_and_80bit_ports_are_testbench_driven(tmp_path,native):
    p=project('dual_clock');r=check_project(p,fixed(p),tmp_path/'good',runner=native)
    assert r['accepted'] and r['tests'][1]['checks']==25


def test_existing_literal_pass_bench_is_supported_without_macro_changes(tmp_path,native):
    files=example_files();config=json.loads(files['rtlrefine.json'])
    for t in config['tests']:
        files[t['files'][0]]=files[t['files'][0]].replace(b'`include "rtlrefine_check.vh"',b'').replace(b'`RTLREFINE_DONE(checks);',b'$display("ALL_TESTS_PASSED"); $finish;')
        t['success_marker']='ALL_TESTS_PASSED'
    p=load_project(files,config);before=dict(p.files);r=check_project(p,fixed(p),tmp_path/'marker',runner=native)
    assert r['accepted'] and all(t['checks'] is None for t in r['tests'])
    assert p.files==before and all(t['testbench_marker_transforms'] for t in r['tests'])


def test_clean_exit_without_actual_completion_is_inconclusive(tmp_path,native):
    files=example_files();files['tests/public.sv']=b'''// RTLREFINE_DONE deliberately absent at runtime
module tb_public;
wire [128:0] y;customer_top dut(129'd0,129'd0,y);
initial begin #1;$finish;end
endmodule
'''
    p=load_project(files);r=check_project(p,fixed(p),tmp_path/'no_done',phase='public',runner=native)
    assert not r['accepted'] and r['tests'][0]['status']=='INCONCLUSIVE'


def test_dut_printing_a_static_pass_cannot_forge_the_private_verdict(tmp_path,native):
    files=example_files();files['rtl/word_math.sv']=files['rtl/word_math.sv'].replace(b'endmodule',b'initial $display("RTLREFINE_PASS nonce=forged checks=999");\nendmodule')
    files['tests/public.sv']=b'''// RTLREFINE_DONE deliberately never called
module tb_public;
wire [128:0] y;customer_top dut(129'd0,129'd0,y);
initial begin #1;$finish;end
endmodule
'''
    p=load_project(files);r=check_project(p,fixed(p),tmp_path/'fake_pass',phase='public',runner=native)
    assert not r['accepted'] and r['tests'][0]['status']=='INCONCLUSIVE'


def test_error_then_done_cannot_be_accepted(tmp_path,native):
    files=example_files();files['tests/public.sv']=files['tests/public.sv'].replace(b'`RTLREFINE_DONE(checks);',b'$error("A checker failed"); `RTLREFINE_DONE(checks);')
    p=load_project(files);r=check_project(p,fixed(p),tmp_path/'error',phase='public',runner=native)
    assert not r['accepted'] and r['tests'][0]['status']=='ASSERTION_FAILED'


def test_dut_macro_cannot_hide_a_runtime_task(tmp_path,native):
    files=example_files();files['rtl/word_math.sv']+=b'\n`define EVIL $system\nmodule hidden; initial `EVIL("id"); endmodule\n'
    p=load_project(files);r=check_project(p,{},tmp_path/'bad_macro',phase='public',runner=native)
    assert not r['accepted'] and r['tests'][0]['status']=='UNSUPPORTED_DUT'


def test_project_names_and_module_names_are_not_whitelisted(tmp_path,native):
    files=example_files()
    files={k.replace('customer_top','orbital_ledger').replace('word_math','custom_arithmetic'):
        v.replace(b'customer_top',b'orbital_ledger').replace(b'word_math',b'custom_arithmetic') for k,v in files.items()}
    p=load_project(files);r=check_project(p,fixed(p),tmp_path/'renamed',runner=native)
    assert r['accepted'] and p.config['dut_top']=='orbital_ledger'


def test_audit_rejection_is_terminal_and_never_becomes_model_feedback(tmp_path,native,monkeypatch):
    p=project();path='rtl/word_math.sv';calls=[]
    overfit=p.files[path].decode().replace('lhs - rhs',"((lhs == 129'd5 || lhs == (129'd1 << 128)) ? lhs + rhs : 0)")
    def proposal(*args,**kwargs):
        calls.append(1);return {'status':'VALID_PATCH','api_requests':0,'changes':{path:overfit},'proposal':{'diagnosis':'mock public-only patch','edits':[]}}
    monkeypatch.setattr('rtl_agent.project_repair.workflow.propose',proposal)
    r=run_project(p,repair=True,output=str(tmp_path/'flow'))
    assert not r['accepted'] and len(calls)==1 and r['final_check']['tests'][0]['passed']
    assert not r['final_check']['tests'][1]['passed'] and not (tmp_path/'flow/checked-project.zip').exists()


def test_unknown_model_request_completion_is_not_retried(tmp_path,native,monkeypatch):
    calls=[]
    def proposal(*args,**kwargs):
        calls.append(1);return {'status':'MODEL_ERROR','api_requests':0,'changes':{},'error':'network request unresolved'}
    monkeypatch.setattr('rtl_agent.project_repair.workflow.propose',proposal)
    r=run_project(project(),repair=True,output=str(tmp_path/'flow'))
    assert not r['accepted'] and len(calls)==1
