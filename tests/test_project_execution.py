import json
from pathlib import Path
import signal
import os
import subprocess
import sys

import pytest

from rtl_agent.common import ROOT
from rtl_agent.project_repair.project import load_project,read_archive
from rtl_agent.project_repair.checker import check_project as reference_check
from rtl_agent.project_repair.execution import PhaseRunner,check_project,wait_for_exit
from rtl_agent.project_repair.runner import ProjectRunner
from rtl_agent.project_repair.examples import example_files


def decision(r):
    return {'status':r['status'],'accepted':r['accepted'],'design_hashes':r['design_hashes'],
            'tests':[{k:t.get(k) for k in ['id','phase','passed','checks','status','interface']} for t in r['tests']]}


@pytest.fixture
def native(tmp_path):
    ok,why=ProjectRunner().probe(tmp_path/'probe')
    if not ok:pytest.skip(why)


@pytest.mark.parametrize('case',['axis-register','wide-math','dual-clock','uart-peer'])
def test_same_frozen_grade_with_fresh_test_compilation_and_simulation(case,tmp_path,native):
    p=load_project(read_archive((ROOT/'demo/general_project_ci'/case/'checked-project.zip').read_bytes()))
    original=reference_check(p,{},tmp_path/'reference')
    optimized=check_project(p,{},tmp_path/'optimized')
    assert decision(optimized)==decision(original)
    commands=[c for t in optimized['tests'] for c in t['commands']]
    assert any(c.get('cache_hit') for c in commands)
    for stage in ['test_preprocess','compile','simulate']:
        rows=[c for c in commands if c['stage']==stage]
        assert len(rows)==len(p.config['tests']) and not any(c['cache_hit'] for c in rows)
    # Each test's actual instantiated DUT configuration is still elaborated
    # independently after its bench/header has been mounted.
    assert sum(c['stage']=='elaborate' and not c['cache_hit'] for c in commands)>=len(p.config['tests'])


def test_cache_is_never_shared_between_checker_calls(tmp_path,native):
    p=load_project(example_files())
    for index in range(2):
        r=check_project(p,{},tmp_path/str(index),phase='public')
        assert not r['accepted']
        assert not any(c['cache_hit'] for t in r['tests'] for c in t['commands'])


def test_changed_source_cannot_reuse_prior_compiler_success(tmp_path,native):
    files=example_files();files['rtl/word_math.sv']=files['rtl/word_math.sv'].replace(b'lhs - rhs',b'lhs + rhs')
    p=load_project(files);runner=PhaseRunner()
    good=reference_check(p,{},tmp_path/'good',phase='public',runner=runner)
    bad=reference_check(p,{'rtl/word_math.sv':p.files['rtl/word_math.sv'].decode().replace('lhs + rhs','lhs - rhs')},tmp_path/'bad',phase='public',runner=runner)
    assert good['accepted'] and not bad['accepted']
    assert not any(c['cache_hit'] for t in bad['tests'] for c in t['commands'])


def test_timeout_remains_unproven_and_cannot_produce_pass(tmp_path,native):
    files=example_files();config=json.loads(files['rtlrefine.json']);config['tests']=config['tests'][:1];config['tests'][0]['timeout_seconds']=.1
    files['tests/public.sv']=b'''`include "rtlrefine_check.vh"
module tb_public;
wire [128:0] result;customer_top dut(129'd0,129'd0,result);
initial begin if(0) `RTLREFINE_DONE(1); forever #1; end
endmodule
'''
    p=load_project(files,config)
    a=reference_check(p,{},tmp_path/'reference');b=check_project(p,{},tmp_path/'optimized')
    assert decision(a)==decision(b) and b['tests'][0]['status']=='TIMEOUT' and not b['accepted']


def test_error_then_done_still_rejected(tmp_path,native):
    files=example_files();files['tests/public.sv']=files['tests/public.sv'].replace(b'`RTLREFINE_DONE(checks);',b'$error("Do not accept this"); `RTLREFINE_DONE(checks);')
    files['rtl/word_math.sv']=files['rtl/word_math.sv'].replace(b'lhs - rhs',b'lhs + rhs')
    p=load_project(files);a=reference_check(p,{},tmp_path/'reference');b=check_project(p,{},tmp_path/'optimized')
    assert decision(a)==decision(b) and not b['accepted'] and b['tests'][0]['status']=='ASSERTION_FAILED'


def test_waiter_preserves_nonzero_exit_and_deadline():
    p=subprocess.Popen([sys.executable,'-c','raise SystemExit(7)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    assert wait_for_exit(p,3)==7
    p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    try:
        with pytest.raises(subprocess.TimeoutExpired):wait_for_exit(p,.02)
    finally:
        os.killpg(p.pid,signal.SIGKILL);p.wait()


def test_launch_policy_matches_reference_exactly(tmp_path,native,monkeypatch):
    actual=subprocess.Popen;captured=[]
    def record(command,*args,**kwargs):
        captured.append({'command':command,'environment':kwargs.get('env'),
                         'new_session':kwargs.get('start_new_session'),'stdin':kwargs.get('stdin')})
        return actual(command,*args,**kwargs)
    monkeypatch.setattr(subprocess,'Popen',record)
    p=load_project(example_files())
    reference_check(p,{},tmp_path/'reference',phase='public');left=list(captured);captured.clear()
    check_project(p,{},tmp_path/'optimized',phase='public');right=list(captured)
    def normalized(rows,name):
        text=json.dumps(rows,sort_keys=True)
        return text.replace(str(tmp_path/name),'/SAME-JOB')
    assert normalized(left,'reference')==normalized(right,'optimized')
