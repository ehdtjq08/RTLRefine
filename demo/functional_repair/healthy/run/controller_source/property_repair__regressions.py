"""Turn public witnesses into immutable, independently expected regressions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from ..common import sha256,write_json
from ..project_repair.project import Project,archive_project,read_archive
from . import portable

DESIGN_KEYS=('dut_top','rtl_files','include_files','include_dirs','data_files','defines','dut_parameters')
CONTRACT_KEYS=('kind','ports','data_width','depth')
FOLDER=portable.FOLDER
README='''# Portable FIFO regressions

From the extracted project root, run:

    python3 -I rtlrefine_regressions/run.py --report regression-report.json

Prerequisites: Linux, Python 3.10+, Icarus Verilog/vvp, bubblewrap and prlimit.
The RTLRefine Docker test build includes the native tools. No API key, model,
Streamlit or Yosys is needed. The runner never falls back to unisolated RTL.

Design source may change: every run compiles a fresh source snapshot and reports
its hashes. The contract, compile configuration, generated benches and runner
are fixed. Regenerate the bundle through RTLRefine if those settings change.
Only these finite regression stimuli are checked; rerun the full application
for the original benches and bounded properties. A zero exit means every
regression passed; exit 1 is a reproduced regression and exit 2 is a setup,
configuration or integrity error. Test expectations come from the contract,
never from the output of a failing implementation. The files in this folder
are tool-owned; keep your own notes elsewhere.

The generated runner and benches are distributed under this license:

MIT License

Copyright (c) 2026 RTLRefine contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

'''


def driver_bytes():return Path(portable.__file__).read_bytes()


def case_from_inputs(inputs,origin):
    clean=[{k:row[k] for k in portable.INPUTS} for row in inputs]
    identity=sha256(json.dumps(clean,sort_keys=True,separators=(',',':')).encode())[:16]
    return {'id':'case_'+identity,'origin':origin,'inputs':clean}


def contract_sequence(c):
    mask=(1<<c['data_width'])-1;d=c['depth'];rows=[]
    def step(rst=0,valid=0,ready=0,data=0):rows.append({'rst':rst,'s_valid':valid,'s_data':data&mask,'m_ready':ready})
    step(rst=1)
    for i in range(d):step(valid=1,data=i+1)
    step();step()
    for i in range(d+2):step(valid=1,ready=1,data=i+9)
    for _ in range(d+1):step(ready=1)
    step(valid=1,data=3);step(valid=1,data=5)
    step(rst=1,valid=1,ready=1,data=mask)
    for i in range(d):step(valid=1,data=i+5)
    for _ in range(d+1):step(ready=1)
    return case_from_inputs(rows,'contract_sequence')


def public_case(properties):
    if properties.get('status')!='COUNTEREXAMPLE' or properties.get('replay',{}).get('status')!='FAILURE_REPRODUCED':return None
    return case_from_inputs(properties['witness'],'public_counterexample')


def inherited_cases(project,c):
    names={p for p in project.files if p==FOLDER or p.startswith(FOLDER+'/')}
    if not names:return []
    manifest_path=FOLDER+'/manifest.json'
    if manifest_path not in project.files:raise ValueError('The '+FOLDER+' folder is reserved for generated regressions; move your files before repair')
    try:manifest=portable.validate_manifest(json.loads(project.files[manifest_path]))
    except (ValueError,TypeError,KeyError) as exc:raise ValueError('Invalid inherited regression bundle: '+str(exc)) from None
    if manifest['contract']!={k:c[k] for k in CONTRACT_KEYS} or manifest['design']!={k:project.config[k] for k in DESIGN_KEYS}:
        raise ValueError('Inherited regressions use a different contract or compile configuration')
    expected={manifest_path,FOLDER+'/run.py',FOLDER+'/README.md'}
    if project.files.get(FOLDER+'/run.py')!=driver_bytes():raise ValueError('Unsupported or changed portable runner')
    if manifest['runner_sha256']!=sha256(driver_bytes()) or project.files.get(FOLDER+'/README.md')!=README.encode():raise ValueError('Changed regression bundle')
    for case in manifest['cases']:
        name=FOLDER+'/'+case['id']+'.sv';expected.add(name)
        if project.files.get(name)!=portable.bench_text(manifest['design'],manifest['contract'],case).encode():raise ValueError('Generated regression bench changed')
    if names!=expected:raise ValueError('Unexpected files in the generated regression folder')
    declared=set(project.config['rtl_files']+project.config['include_files']+project.config['data_files'])
    declared.update(p for t in project.config['tests'] for p in t['files']+t['include_files']+t['data_files'])
    if declared & names:raise ValueError('Generated regressions cannot be editable design or original testbench files')
    return [{k:case[k] for k in ('id','origin','inputs')} for case in manifest['cases']]


def merge_cases(*groups):
    result=[];seen=set()
    for group in groups:
        for case in group:
            if not case or case['id'] in seen:continue
            seen.add(case['id']);result.append(case)
    if len(result)>16:raise ValueError('Regression bundle exceeds 16 retained input traces')
    return result


def with_bundle(project,c,cases,changes=None):
    cases=merge_cases(cases);design={k:project.config[k] for k in DESIGN_KEYS};contract={k:c[k] for k in CONTRACT_KEYS}
    files={p:v for p,v in project.files.items() if not p.startswith(FOLDER+'/')}
    files.update({p:text.encode() for p,text in (changes or {}).items()})
    manifest={'schema_version':1,'producer':'RTLRefine','generator_version':portable.VERSION,'design':design,'contract':contract,
              'cases':[],'source_hashes':{p:sha256(files[p]) for p in design['rtl_files']+design['include_files']+design['data_files']},
              'runner_sha256':sha256(driver_bytes())}
    for case in cases:
        text=portable.bench_text(design,contract,case)
        manifest['cases'].append({**case,'bench_sha256':sha256(text.encode())})
        files[FOLDER+'/'+case['id']+'.sv']=text.encode()
    portable.validate_manifest(manifest)
    files[FOLDER+'/run.py']=driver_bytes();files[FOLDER+'/README.md']=README.encode()
    files[FOLDER+'/manifest.json']=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    return Project(files,project.config)


def check_bundle(project,directory,*,standalone=False):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    # Archive round-trip executes the same bytes and normalized config we export.
    files=read_archive(archive_project(project));snapshot=directory/'project';snapshot.mkdir()
    if files.get(FOLDER+'/run.py')!=driver_bytes():raise ValueError('Only the canonical generated runner may execute')
    for name,data in files.items():
        path=snapshot/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    if standalone:
        report=directory/'standalone-report.json';stdout=directory/'standalone-stdout.json';stderr=directory/'standalone-stderr.log'
        env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'HOME':'/nonexistent','LANG':'C','LC_ALL':'C'}
        command=[sys.executable,'-I',str(snapshot/FOLDER/'run.py'),'--root',str(snapshot),'--report',str(report)]
        try:
            with stdout.open('wb') as out,stderr.open('wb') as err:
                p=subprocess.run(command,cwd=snapshot,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=195)
            result=json.loads(report.read_text()) if report.exists() else {'status':'RUNNER_ERROR','accepted':False,'tests':[],'new_model_calls':0}
            expected=0 if result['accepted'] else 1 if result['status']=='REGRESSION_FAILED' else 2
            if p.returncode!=expected:result.update(status='RUNNER_PROTOCOL_ERROR',accepted=False)
            result.update(standalone_exit_code=p.returncode,python_isolated=True,canonical_runner_verified=True)
        except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
            result={'status':'RUNNER_UNPROVEN','accepted':False,'tests':[],'new_model_calls':0,'error':str(exc)}
    else:result=portable.run_suite(snapshot)
    write_json(directory/'regression-result.json',result)
    return result


def failed_public_feedback(result,cases):
    failed={t['id'] for t in result.get('tests',[]) if not t['passed']}
    return {'status':result['status'],'failures':[{'id':t['id'],'log_tail':(t.get('simulation') or t['compile'])['log_tail'][-4000:]}
            for t in result.get('tests',[]) if t['id'] in failed],
            'public_regression_inputs':[case['inputs'] for case in cases if case['id'] in failed]}
