"""Run immutable self-checking benches; a bare clean exit is not a pass."""
from __future__ import annotations

import json
from pathlib import Path
import re
import secrets

from ..common import sha256,write_json
from .policy import validate_design,validate_patch
from .runner import ProjectRunner


def _write(directory,name,data):
    path=directory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)


def _flags(project):
    flags=[]
    for name,value in project.config['defines'].items():flags+=['-D'+name+'='+value]
    for path in project.config['include_dirs']:flags+=['-I','./'+path]
    return flags


def _interface(vvp,top):
    """Icarus exposes the elaborated width of every port, including >64 bits."""
    result=[];current=None
    for line in vvp.splitlines():
        scope=re.search(r'\.scope (\S+), "([^"]+)" "([^"]+)"',line)
        if scope:
            current={'instance':scope[2],'ports':[]} if scope[1]=='module' and scope[3]==top else None
            if current is not None:result.append(current)
        port=re.search(r'\.port_info (\d+) /(INPUT|OUTPUT|INOUT) (\d+) "([^"]+)"',line)
        if port and current is not None:current['ports'].append({'index':int(port[1]),'direction':port[2],'width':int(port[3]),'name':port[4]})
    return sorted(result,key=lambda x:(x['instance'],str(x['ports'])))


def check_test(project,changes,test,directory,runner,*,expected_interface=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False);(directory/'__rtlrefine').mkdir()
    config=project.config;commands=[]
    source_files=config['rtl_files']+config['include_files']
    for name in source_files:_write(directory,name,changes.get(name,project.files[name].decode()).encode())
    for name in config['data_files']:_write(directory,name,project.files[name])
    source_hashes={name:sha256((directory/name).read_bytes()) for name in source_files+config['data_files']}
    record={'id':test['id'],'phase':test['phase'],'top':test['top'],'passed':False,'checks':0,'status':'TOOL_UNAVAILABLE','commands':commands,
        'source_hashes':source_hashes,'oracle':'User-supplied immutable self-checking testbench','clock_semantics':'Testbench-driven Icarus four-state simulation; no port-width or single-clock trace harness'}
    flags=_flags(project)
    commands.append(runner.run('preprocess',['-g2012','-E','-o','__rtlrefine/design.v',*flags,*['./'+p for p in config['rtl_files']]],directory))
    if commands[-1]['status']!='PASS':record['status']='PREPROCESS_FAILED'
    else:
        expanded=(directory/'__rtlrefine/design.v').read_text()
        try:
            validate_design(expanded,test_tops=[t['top'] for t in config['tests']],data_files=config['data_files'])
        except ValueError as exc:record.update(status='UNSUPPORTED_DUT',error=str(exc))
        else:
            # Standalone DUT elaboration prevents dependence on testbench tasks,
            # signals or checker modules before running that testbench.
            params=['-P'+config['dut_top']+'.'+k+'='+v for k,v in config['dut_parameters'].items()]
            commands.append(runner.run('elaborate',['-g2012','-t','null','-s',config['dut_top'],*params,'./__rtlrefine/design.v'],directory))
            if commands[-1]['status']!='PASS':record['status']='DUT_COMPILE_FAILED'
            else:
                nonce=secrets.token_hex(16)
                transforms=[]
                for name in test['files']+test['data_files']:
                    value=project.files[name]
                    if name in test['files'] and test.get('success_marker'):
                        text=value.decode();marker=test['success_marker']
                        pattern=r'(\$(?:display|write)\s*\(\s*)"'+re.escape(marker)+r'"(\s*\))'
                        text,count=re.subn(pattern,lambda m:m[1]+'"RTLREFINE_MARKER nonce='+nonce+'"'+m[2],text)
                        if count:transforms.append({'file':name,'original_sha256':sha256(value),'executed_sha256':sha256(text.encode()),'completion_literals_tagged':count})
                        value=text.encode()
                    _write(directory,name,value)
                record['testbench_marker_transforms']=transforms
                header='''`ifndef RTLREFINE_CHECK_VH
`define RTLREFINE_CHECK_VH
`define RTLREFINE_DONE(CHECKS) begin $display("RTLREFINE_PASS nonce=NONCE checks=%0d", (CHECKS)); $finish; end
`endif
'''.replace('NONCE',nonce)
                (directory/'rtlrefine_check.vh').write_text(header)
                test_hashes={name:sha256((directory/name).read_bytes()) for name in test['files']+test['data_files']+['rtlrefine_check.vh']}
                params=['-P'+test['top']+'.'+k+'='+v for k,v in test['parameters'].items()]
                commands.append(runner.run('compile',['-g2012','-s',test['top'],'-o','__rtlrefine/simulation.vvp','-I.',*flags,*params,
                    './__rtlrefine/design.v',*['./'+p for p in test['files']]],directory))
                if commands[-1]['status']!='PASS':record['status']='TEST_COMPILE_FAILED'
                else:
                    interface=_interface((directory/'__rtlrefine/simulation.vvp').read_text(),config['dut_top'])
                    record['interface']=interface
                    if not interface:record.update(status='INVALID_TEST',error='Testbench did not instantiate the declared DUT top')
                    elif expected_interface is not None and interface!=expected_interface:record.update(status='INTERFACE_CHANGED',error='Elaborated DUT interface changed')
                    else:
                        commands.append(runner.run('simulate',['__rtlrefine/simulation.vvp'],directory,timeout=test['timeout_seconds']))
                        log=(directory/'simulate.log').read_text(errors='replace')
                        markers=re.findall(r'^RTLREFINE_PASS nonce='+nonce+r' checks=(\d+)\s*$',log,re.M)
                        errors=bool(re.search(r'^(?:ERROR|FATAL):',log,re.M))
                        record['checks']=max(map(int,markers),default=0)
                        if test.get('success_marker'):
                            completed=re.findall(r'^RTLREFINE_MARKER nonce='+nonce+r'\s*$',log,re.M)
                            record['checks']=None
                            record['passed']=commands[-1]['status']=='PASS' and len(completed)==1 and not errors
                        else:record['passed']=commands[-1]['status']=='PASS' and len(markers)==1 and not errors and record['checks']>=test['minimum_checks']
                        record['status']='PASS' if record['passed'] else 'TIMEOUT' if commands[-1]['status']=='TIMEOUT' else 'ASSERTION_FAILED' if errors or commands[-1]['status']=='FAIL' else 'INCONCLUSIVE'
                        record['log_tail']=log[-12000:]
                record['verification_hashes']=test_hashes
                for name,expected in {**source_hashes,**test_hashes}.items():
                    if sha256((directory/name).read_bytes())!=expected:record.update(passed=False,status='WORKER_MUTATED_INPUT',error='Readonly input changed')
    record['wall_seconds']=sum(c['wall_seconds'] for c in commands)
    failures=[directory/(c['stage']+'.log') for c in commands if c['status']!='PASS']
    if failures and 'log_tail' not in record:record['log_tail']=failures[-1].read_text(errors='replace')[-12000:]
    write_json(directory/'check.json',record);return record


def check_project(project,changes,directory,*,phase='all',runner=None,interfaces=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False);runner=runner or ProjectRunner()
    if changes:validate_patch(project,changes)
    ok,why=runner.probe(directory/'isolation')
    if not ok:raise RuntimeError('Native isolation unavailable: '+why)
    tests=project.config['tests'] if phase=='all' else [t for t in project.config['tests'] if t['phase']==phase]
    rows=[check_test(project,changes,t,directory/t['id'],runner,expected_interface=(interfaces or {}).get(t['id'])) for t in tests]
    accepted=bool(rows) and all(r['passed'] for r in rows)
    result={'status':'PROVIDED_TESTS_PASS' if accepted else 'PROVIDED_TESTS_NOT_PASSED','accepted':accepted,'phase':phase,'tests':rows,
        'project_id':project.identity,'design_hashes':{p:sha256(changes.get(p,v.decode()).encode()) for p,v in project.files.items() if p in project.config['rtl_files']+project.config['include_files']},
        'verification_scope':'Only the supplied testbenches and configuration; not unbounded correctness, synthesis timing or physical CDC safety',
        'shared_compilation_speed_claim_applies':False,'new_model_calls':0}
    write_json(directory/'verification.json',result);return result
