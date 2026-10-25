"""Fast discovery screening; exact final-source verification remains separate."""
from pathlib import Path
import shutil
import time

from ..common import sha256,write_json
from ..known_bugs_v2.engine import harness,run_trace,compile_candidate
from ..known_bugs_v2.runner import BenchmarkRunner
from ..known_bugs_v2.cases import source_policy
from ..known_bugs_v2.evaluator import _editable_ports
from .schema import instrument,partition,SELECTOR


def batch_harness(case):
    text=harness(case['ports'],case['clock'],case['top'])
    text=text.replace(' V'+case['top']+' dut;',
        ' unsigned selector=0; std::ifstream selected("selector.txt"); if(!(selected>>selector) || selector>128) return 7;\n V'+case['top']+' dut;\n dut.'+SELECTOR+'=selector;')
    return text


def screen(source,dependencies,case,pool,trace,directory,*,runner=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False);runner=runner or BenchmarkRunner()
    ok,why=runner.probe(directory/'isolation')
    if not ok:raise RuntimeError(why)
    started=time.monotonic();supported,fallback=partition(source,pool)
    policy_ports=case['ports'] if case['top']==case['edited_module'] else _editable_ports(source)
    source_policy(source,source,policy_ports)
    for candidate in pool:source_policy(candidate['rtl'],source,policy_ports)
    if not supported:raise ValueError('No supported candidates for batch screening')
    instrumented,deps,mapping=instrument(source,dependencies,case,supported)
    compiled=directory/'compiled';compiled.mkdir();(compiled/'candidate.v').write_text(instrumented)
    (compiled/'dependencies.v').write_text(deps);(compiled/'harness.cpp').write_text(batch_harness(case))
    commands=[runner.run('translate',compiled,case['top'])]
    if commands[-1]['status']=='PASS':commands.append(runner.run('build',compiled,case['top']))
    write_json(directory/'selector_map.json',mapping)
    record={'status':'COMPILE_FAILED','results':{},'supported':len(supported),'fallback_ids':[p['id'] for p in fallback],
        'fallback_reasons':{p['id']:p['batch_fallback_reason'] for p in fallback},'commands':commands,
        'original_source_sha256':sha256(source.encode()),'new_model_calls':0,'screening_is_not_final_admission':True}
    if len(commands)!=2 or commands[-1]['status']!='PASS':
        record['wall_seconds']=time.monotonic()-started;write_json(directory/'screen.json',record);return record
    # Mandatory inactive-selector control: its complete output stream must be
    # identical to an ordinary uninstrumented build on the same public inputs.
    ordinary=directory/'ordinary_control'
    control_commands=compile_candidate(source,dependencies,case['ports'],case['clock'],case['top'],ordinary,runner)
    record['control_commands']=control_commands
    if len(control_commands)!=2 or control_commands[-1]['status']!='PASS':raise RuntimeError('Uninstrumented control compilation failed')
    original_capture=run_trace(ordinary,trace,case['top'],runner,capture=True)
    (compiled/'selector.txt').write_text('0\n')
    batch_capture=run_trace(compiled,trace,case['top'],runner,capture=True)
    same=original_capture['passed'] and batch_capture['passed'] and (ordinary/'observed.hex').read_bytes()==(compiled/'observed.hex').read_bytes()
    record['inactive_selector_exact_output_match']=same
    if not same:
        record['status']='CONTROL_MISMATCH';record['wall_seconds']=time.monotonic()-started;write_json(directory/'screen.json',record);return record
    for identity,selector in mapping.items():
        (compiled/'selector.txt').write_text(str(selector)+'\n')
        result=run_trace(compiled,trace,case['top'],runner)
        record['results'][identity]={k:result[k] for k in ('passed','cycles','comparisons','mismatch_count','first_mismatches')}
        (directory/(identity+'.log')).write_bytes((compiled/'simulate.log').read_bytes())
    record['status']='COMPLETE';record['wall_seconds']=time.monotonic()-started
    write_json(directory/'screen.json',record);return record


def standalone_screen(source,dependencies,case,candidate,trace,directory,runner):
    directory.mkdir(parents=True,exist_ok=False)
    ports=case['ports'] if case['top']==case['edited_module'] else _editable_ports(source)
    source_policy(candidate['rtl'],source,ports)
    compiled=directory/'compiled'
    commands=compile_candidate(candidate['rtl'],dependencies,case['ports'],case['clock'],case['top'],compiled,runner)
    if len(commands)!=2 or commands[-1]['status']!='PASS':
        record={'passed':False,'cycles':0,'comparisons':0,'mismatch_count':None,'first_mismatches':[],'compile_failed':True}
    else:
        result=run_trace(compiled,trace,case['top'],runner)
        record={k:result[k] for k in ('passed','cycles','comparisons','mismatch_count','first_mismatches')}
    write_json(directory/'result.json',{'commands':commands,**record});return record


def screen_all(source,dependencies,case,pool,trace,directory,*,runner=None):
    """Cover the identical complete pool, with standalone compatibility fallback."""
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False);runner=runner or BenchmarkRunner();start=time.monotonic()
    by={p['id']:p for p in pool};result={};batch=None;fallback=list(by)
    try:
        batch=screen(source,dependencies,case,pool,trace,directory/'batch',runner=runner)
        if batch['status']=='COMPLETE':result.update(batch['results']);fallback=batch['fallback_ids']
    except ValueError as exc:
        write_json(directory/'batch_unavailable.json',{'reason':str(exc),'fallback':'all candidates checked independently'})
    for identity in fallback:
        result[identity]=standalone_screen(source,dependencies,case,by[identity],trace,directory/identity,runner)
    record={'status':'COMPLETE','results':result,'wall_seconds':time.monotonic()-start,
        'candidates':len(pool),'batched_candidates':len(pool)-len(fallback),'standalone_fallbacks':len(fallback),
        'control_match':batch.get('inactive_selector_exact_output_match') if batch else None,
        'new_model_calls':0,'scope':'Complete-pool public-trace screening, not final repair admission or unbounded equivalence'}
    write_json(directory/'complete.json',record);return record
