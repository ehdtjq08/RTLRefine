"""Self-contained regression runner; copied verbatim into checked FIFO exports.

Only Python's standard library is used. Native RTL is always namespace-isolated.
The command-line entry requires -I so a project cannot shadow standard modules.
"""
import sys

if __name__ == '__main__' and not sys.flags.isolated:
    print('Run with isolated Python: python3 -I rtlrefine_regressions/run.py',file=sys.stderr)
    raise SystemExit(2)

import argparse
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import secrets
import shutil
import signal
import subprocess
import tempfile
import time

VERSION=1
FOLDER='rtlrefine_regressions'
MARKER='RTLREFINE_REGRESSION_PASS'
INPUTS=('rst','s_valid','s_data','m_ready')
PORTS={'clk':('INPUT',1),'rst':('INPUT',1),'s_valid':('INPUT',1),'s_ready':('OUTPUT',1),
       's_data':('INPUT',None),'m_valid':('OUTPUT',1),'m_ready':('INPUT',1),'m_data':('OUTPUT',None)}
IDENTIFIER=re.compile(r'[A-Za-z_][A-Za-z0-9_$]*\Z')
NUMBER=re.compile(r"(?:\d+|\d+'[sS]?[bBoOdDhH][0-9a-fA-F_]+)\Z")
LEX=re.compile(r'(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)|(?P<string>"(?:\\.|[^"\\])*")|(?P<escaped>\\[^\s]+)|(?P<id>[A-Za-z_$][A-Za-z0-9_$]*)|(?P<other>.)')


def digest(data):return hashlib.sha256(data).hexdigest()


def relative(name):
    if not isinstance(name,str) or not name or '\\' in name or any(ord(c)<32 for c in name):raise ValueError('Invalid relative path')
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or ':' in p.parts[0] or p.parts[0].startswith('__rtlrefine'):raise ValueError('Unsafe project path')
    if any(v in {'.git','.ssh','.aws'} or v.startswith('.env') for v in p.parts):raise ValueError('Credential paths are not design inputs')
    if str(p)=='.':raise ValueError('Empty file path')
    return str(p)


def read_file(root,name):
    name=relative(name);path=root/name
    if not path.resolve().is_relative_to(root.resolve()) or any(p.is_symlink() for p in [path,*path.parents] if p!=root.parent):
        raise ValueError('Symlink or external input path')
    if not path.is_file() or path.stat().st_size>4*1024**2:raise ValueError('Missing or oversized input: '+name)
    return path.read_bytes()


def expected_trace(rows,width,depth):
    """Compute expected transfers exclusively from the contract and inputs."""
    queue=[];result=[]
    if not isinstance(rows,list) or not 1<=len(rows)<=128:raise ValueError('A regression needs 1–128 input steps')
    for i,row in enumerate(rows):
        if not isinstance(row,dict) or set(row)!=set(INPUTS) or any(type(v) is not int for v in row.values()):raise ValueError('Invalid stimulus row')
        if any(row[k] not in (0,1) for k in ('rst','s_valid','m_ready')) or not 0<=row['s_data']<1<<width:
            raise ValueError('Stimulus exceeds declared bit widths')
        if i==0 and row['rst']!=1:raise ValueError('Regression must start with reset')
        if row['rst']:queue=[]
        valid=int(not row['rst'] and bool(queue))
        ready=int(not row['rst'] and (len(queue)<depth or (bool(queue) and row['m_ready'])))
        result.append({**row,'step':i+1,'expected_valid':valid,'expected_ready':ready,
                       'expected_data':queue[0] if valid else None,'expected_occupancy':len(queue)})
        if not row['rst']:
            if valid and row['m_ready']:queue.pop(0)
            if ready and row['s_valid']:queue.append(row['s_data'])
        result[-1].update(after_valid=int(not row['rst'] and bool(queue)),
                          after_ready=int(not row['rst'] and (len(queue)<depth or (bool(queue) and row['m_ready']))),
                          after_data=queue[0] if not row['rst'] and queue else None)
    return result


def bench_text(design,contract,case):
    trace=expected_trace(case['inputs'],contract['data_width'],contract['depth'])
    params=','.join('.'+k+'('+v+')' for k,v in sorted(design['dut_parameters'].items()))
    instance=design['dut_top']+(' #('+params+')' if params else '')+' dut('+','.join('.'+v+'('+k+')' for k,v in sorted(contract['ports'].items()))+');'
    calls=[]
    for row in trace:
        data=row['expected_data'];after=row['after_data']
        values=[row['step'],row['rst'],row['s_valid'],row['s_data'],row['m_ready'],row['expected_ready'],row['expected_valid'],data or 0,int(data is not None),
                row['after_ready'],row['after_valid'],after or 0,int(after is not None)]
        calls.append('step('+','.join(map(str,values))+');')
    return f'''// Generated from public input stimuli and an independent FIFO contract.
// No observed output from the failing DUT is used as an expected value.
module __rtlrefine_regression_{case['id']};
reg clk=0,rst=0,s_valid=0,m_ready=0;
reg [{contract['data_width']-1}:0] s_data=0;
wire s_ready,m_valid;
wire [{contract['data_width']-1}:0] m_data;
integer checks=0;
{instance}
task step;
input integer cycle,reset_value,valid_value,data_value,ready_value,expect_ready,expect_valid,expect_data,check_data,after_ready,after_valid,after_data,check_after;
begin
    clk=0;rst=reset_value;s_valid=valid_value;s_data=data_value;m_ready=ready_value;#2;
    if(s_ready !== expect_ready[0]) $fatal(1,"step=%0d ready actual=%b expected=%b",cycle,s_ready,expect_ready[0]);
    checks=checks+1;
    if(m_valid !== expect_valid[0]) $fatal(1,"step=%0d valid actual=%b expected=%b",cycle,m_valid,expect_valid[0]);
    checks=checks+1;
    if(check_data) begin
        if(m_data !== expect_data[{contract['data_width']-1}:0]) $fatal(1,"step=%0d payload actual=%h expected=%h",cycle,m_data,expect_data);
        checks=checks+1;
    end
    clk=1;#1;
    if(s_ready !== after_ready[0]) $fatal(1,"step=%0d post-edge ready actual=%b expected=%b",cycle,s_ready,after_ready[0]);
    checks=checks+1;
    if(m_valid !== after_valid[0]) $fatal(1,"step=%0d post-edge valid actual=%b expected=%b",cycle,m_valid,after_valid[0]);
    checks=checks+1;
    if(check_after) begin
        if(m_data !== after_data[{contract['data_width']-1}:0]) $fatal(1,"step=%0d post-edge payload actual=%h expected=%h",cycle,m_data,after_data);
        checks=checks+1;
    end
    clk=0;#1;
end
endtask
initial begin
'''+ '\n'.join(calls)+f'\n$display("{MARKER} checks=%0d",checks);\n$finish;end\nendmodule\n'


def validate_manifest(value):
    required={'schema_version','producer','generator_version','contract','design','cases','source_hashes','runner_sha256'}
    if not isinstance(value,dict) or set(value)!=required or value['schema_version']!=1 or value['producer']!='RTLRefine' or value['generator_version']!=VERSION:
        raise ValueError('Unsupported regression manifest')
    c=value['contract'];d=value['design']
    if not isinstance(c,dict) or set(c)!={'kind','ports','data_width','depth'} or c['kind']!='ready_valid_fifo':raise ValueError('Unsupported regression contract')
    if type(c['data_width']) is not int or not 1<=c['data_width']<=16 or type(c['depth']) is not int or not 2<=c['depth']<=8:raise ValueError('Unsupported FIFO dimensions')
    if set(c['ports'])!=set(PORTS) or len(set(c['ports'].values()))!=8 or any(not isinstance(v,str) or not IDENTIFIER.fullmatch(v) for v in c['ports'].values()):raise ValueError('Invalid port mapping')
    if not isinstance(d,dict) or set(d)!={'dut_top','rtl_files','include_files','include_dirs','data_files','defines','dut_parameters'} or not isinstance(d['dut_top'],str) or not IDENTIFIER.fullmatch(d['dut_top']):raise ValueError('Invalid design configuration')
    for key in ('rtl_files','include_files','data_files'):
        if not isinstance(d[key],list) or len(d[key])>256 or len(set(d[key]))!=len(d[key]):raise ValueError('Invalid design file list')
        for name in d[key]:
            if relative(name)!=name or name.startswith(FOLDER+'/'):raise ValueError('Invalid design input')
    if not d['rtl_files'] or set(d['rtl_files'])&set(d['include_files']+d['data_files']):raise ValueError('Overlapping design roles')
    if any(Path(n).suffix not in {'.v','.sv','.vh','.svh'} for n in d['rtl_files']+d['include_files']):raise ValueError('Expected RTL source files')
    if not isinstance(d['include_dirs'],list) or len(d['include_dirs'])>256:raise ValueError('Invalid include directories')
    for name in d['include_dirs']:
        if name!='.':relative(name)
    for key in ('defines','dut_parameters'):
        if not isinstance(d[key],dict) or len(d[key])>32:raise ValueError('Invalid constants')
        for name,text in d[key].items():
            if not IDENTIFIER.fullmatch(name) or not isinstance(text,str) or len(text)>120 or any(v in text for v in '\n\r\x00'):raise ValueError('Invalid constant')
            if key=='dut_parameters' and not NUMBER.fullmatch(text):raise ValueError('Use constant numeric parameters')
    if not isinstance(value['cases'],list) or not 1<=len(value['cases'])<=16:raise ValueError('Expected 1–16 regression cases')
    ids=set()
    for case in value['cases']:
        if not isinstance(case,dict) or set(case)!={'id','origin','inputs','bench_sha256'} or not re.fullmatch('case_[0-9a-f]{16}',case['id']) or case['id'] in ids:
            raise ValueError('Invalid regression case')
        if case['origin'] not in {'public_counterexample','contract_sequence'}:raise ValueError('Invalid case origin')
        identity='case_'+digest(json.dumps(case['inputs'],sort_keys=True,separators=(',',':')).encode())[:16]
        if case['id']!=identity:raise ValueError('Regression input identity changed')
        ids.add(case['id']);expected_trace(case['inputs'],c['data_width'],c['depth'])
        if digest(bench_text(d,c,case).encode())!=case['bench_sha256']:raise ValueError('Regression oracle checksum changed')
    declared=set(d['rtl_files']+d['include_files']+d['data_files'])
    if not isinstance(value['source_hashes'],dict) or set(value['source_hashes'])!=declared:raise ValueError('Incomplete source fingerprints')
    if any(not isinstance(v,str) or not re.fullmatch('[0-9a-f]{64}',v) for v in [*value['source_hashes'].values(),value['runner_sha256']]):raise ValueError('Invalid checksum')
    return value


def validate_dut(source):
    for match in LEX.finditer(source):
        if match.lastgroup!='id':continue
        word=match.group()
        if word.startswith('$') and word not in {'$clog2','$bits','$signed','$unsigned'}:raise ValueError('Unsupported DUT simulator task: '+word)
        if word in {'force','release','bind','export','class','program','checker','assume','assert','cover','restrict'}:raise ValueError('Unsupported DUT checker construct: '+word)


class Native:
    def __init__(self,directory):
        self.directory=directory;self.deadline=time.monotonic()+180
        self.tools={name:shutil.which(name) for name in ('iverilog','vvp','bwrap','prlimit')}
        if not all(self.tools.values()):raise RuntimeError('Install Icarus Verilog, bubblewrap and util-linux; no unisolated fallback is used')
        paths=[str(Path(self.tools[n]).parent) for n in ('iverilog','vvp')]
        self.environment={'PATH':':'.join(dict.fromkeys(paths+['/usr/bin','/bin'])),'HOME':'/nonexistent','LANG':'C','LC_ALL':'C'}

    def sandbox(self,command):
        args=[self.tools['bwrap'],'--unshare-all','--die-with-parent','--new-session','--cap-drop','ALL','--clearenv']
        for path in ('/usr','/bin','/lib','/lib64','/etc/ld.so.cache'):
            if Path(path).exists():args+=['--ro-bind',path,path]
        prefixes={str(Path(self.tools[n]).parent.parent) for n in ('iverilog','vvp') if not self.tools[n].startswith(('/usr/','/bin/'))}
        for prefix in prefixes:
            if prefix in {'/',str(Path.home()),'/home','/tmp'}:raise RuntimeError('Unsafe native tool prefix')
            args+=['--ro-bind',prefix,prefix]
        args+=['--proc','/proc','--dev','/dev','--tmpfs','/tmp','--bind',str(self.directory),'/work','--chdir','/work']
        for path in self.directory.rglob('*'):
            if path.is_file() and ('__rtlrefine' not in path.relative_to(self.directory).parts or 'frozen' in path.relative_to(self.directory).parts):
                args+=['--ro-bind',str(path),'/work/'+path.relative_to(self.directory).as_posix()]
        for k,v in self.environment.items():args+=['--setenv',k,v]
        return args+['--setenv','TMPDIR','/tmp','--',*command]

    def run(self,label,tool,args,timeout=25):
        private=self.directory/'__rtlrefine';private.mkdir(exist_ok=True);log=private/(label+'.log');started=time.monotonic();process=None
        record={'status':'ERROR','network':False,'api_credentials_inherited':False,'stage':label}
        try:
            limit=min(timeout,self.deadline-started)
            if limit<=0:raise RuntimeError('Regression time budget exhausted')
            command=self.sandbox([self.tools[tool],*args])
            command=[self.tools['prlimit'],'--core=0','--as=2147483648','--cpu=60:61','--fsize=16777216','--nofile=128','--',*command]
            with log.open('wb') as f:
                process=subprocess.Popen(command,cwd=self.directory,env=self.environment,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
                code=process.wait(timeout=limit)
            record.update(status='PASS' if code==0 else 'FAIL',returncode=code)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.wait();record['status']='TIMEOUT'
        except (OSError,RuntimeError) as exc:log.write_text(str(exc)+'\n')
        record.update(seconds=time.monotonic()-started,log_tail=log.read_text(errors='replace')[-12000:])
        return record


def interface_matches(vvp,top,c):
    ports={};current=False;instances=0
    for line in vvp.splitlines():
        scope=re.search(r'\.scope (\S+), "([^"]+)" "([^"]+)"',line)
        if scope:
            current=scope[1]=='module' and scope[3]==top
            if current:instances+=1
        port=re.search(r'\.port_info \d+ /(INPUT|OUTPUT|INOUT) (\d+) "([^"]+)"',line)
        if current and port:ports[port[3]]=(port[1],int(port[2]))
    expected={c['ports'][p]:(direction,width or c['data_width']) for p,(direction,width) in PORTS.items()}
    return instances==1 and ports==expected


def run_suite(root):
    root=Path(root).resolve();result={'status':'INTEGRITY_ERROR','accepted':False,'tests':[],'new_model_calls':0,'scope':'Only the bundled finite input regressions, not a fresh formal proof'}
    try:
        metadata=read_file(root,FOLDER+'/manifest.json')
        if len(metadata)>1024**2:raise ValueError('Oversized regression manifest')
        manifest=validate_manifest(json.loads(metadata));d=manifest['design'];c=manifest['contract']
        project_config=json.loads(read_file(root,'rtlrefine.json'))
        declared={k:project_config.get(k,{} if k in {'defines','dut_parameters'} else [] if k!='dut_top' else '') for k in d}
        for key in ('defines','dut_parameters'):declared[key]={k:str(v) for k,v in declared[key].items()}
        current_contract=json.loads(read_file(root,'fifo_contract.json'))
        if declared!=d or {k:current_contract.get(k) for k in c}!=c:
            result.update(status='CONFIGURATION_CHANGED',error='Project/contract configuration changed; regenerate regressions after a full check');return result
        if digest(read_file(root,FOLDER+'/run.py'))!=manifest['runner_sha256']:raise ValueError('Regression runner checksum changed')
        for case in manifest['cases']:
            if read_file(root,FOLDER+'/'+case['id']+'.sv')!=bench_text(d,c,case).encode():raise ValueError('Regression bench changed: '+case['id'])
        sources={name:read_file(root,name) for name in d['rtl_files']+d['include_files']+d['data_files']}
        if sum(map(len,sources.values()))>32*1024**2:raise ValueError('Source snapshot exceeds 32 MiB')
        result.update(source_hashes={n:digest(v) for n,v in sources.items()},recorded_source_hashes=manifest['source_hashes'])
        result['source_changed']=result['source_hashes']!=manifest['source_hashes']
        with tempfile.TemporaryDirectory(prefix='rtlrefine-regress-',dir='/tmp') as temp:
            work=Path(temp)
            for name,data in sources.items():
                path=work/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            frozen=work/'__rtlrefine/frozen';frozen.mkdir(parents=True)
            runner=Native(work)
            flags=[part for k,v in d['defines'].items() for part in ['-D'+k+'='+v]]
            flags += [part for directory in d['include_dirs'] for part in ['-I','./'+directory]]
            pre=runner.run('preprocess','iverilog',['-g2012','-E','-o','__rtlrefine/expanded.v',*flags,*['./'+n for n in d['rtl_files']]])
            result['preprocess']=pre
            if pre['status']!='PASS':result['status']='PREPROCESS_FAILED';return result
            expanded=(work/'__rtlrefine/expanded.v').read_text()
            try:validate_dut(expanded)
            except ValueError as exc:result.update(status='UNSUPPORTED_DESIGN',error=str(exc));return result
            (frozen/'design.v').write_text(expanded)
            params=['-P'+d['dut_top']+'.'+k+'='+v for k,v in d['dut_parameters'].items()]
            elaborated=runner.run('elaborate','iverilog',['-g2012','-s',d['dut_top'],'-o','__rtlrefine/dut.vvp',*params,'__rtlrefine/frozen/design.v'])
            result['elaboration']=elaborated
            if elaborated['status']!='PASS':result['status']='ELABORATION_FAILED';return result
            if not interface_matches((work/'__rtlrefine/dut.vvp').read_text(),d['dut_top'],c):result['status']='INTERFACE_CHANGED';return result
            for case in manifest['cases']:
                nonce=secrets.token_hex(16);bench=bench_text(d,c,case)
                executed=bench.replace(MARKER,MARKER+' nonce='+nonce)
                bench_path='__rtlrefine/frozen/'+case['id']+'.sv';(work/bench_path).write_text(executed)
                binary='__rtlrefine/'+case['id']+'.vvp'
                compiled=runner.run(case['id']+'_compile','iverilog',['-g2012','-s','__rtlrefine_regression_'+case['id'],'-o',binary,'__rtlrefine/frozen/design.v',bench_path])
                simulated=runner.run(case['id']+'_simulate','vvp',[binary]) if compiled['status']=='PASS' else None
                trace=expected_trace(case['inputs'],c['data_width'],c['depth']);checks=sum(4+int(row['expected_data'] is not None)+int(row['after_data'] is not None) for row in trace)
                matches=re.findall(r'^'+MARKER+' nonce='+nonce+r' checks=(\d+)\s*$',simulated['log_tail'],re.M) if simulated else []
                passed=bool(simulated and simulated['status']=='PASS' and matches==[str(checks)] and not re.search(r'^(ERROR|FATAL):',simulated['log_tail'],re.M))
                failed_assertion=bool(simulated and simulated['status']=='FAIL' and re.search(r'^(ERROR|FATAL):',simulated['log_tail'],re.M))
                status='PASS' if passed else 'ASSERTION_FAILED' if failed_assertion else 'UNPROVEN'
                result['tests'].append({'id':case['id'],'origin':case['origin'],'status':status,'passed':passed,'steps':len(trace),'expected_checks':checks,
                                        'compile':compiled,'simulation':simulated,'original_bench_sha256':digest(bench.encode()),'executed_bench_sha256':digest(executed.encode())})
            result['accepted']=bool(result['tests']) and all(t['passed'] for t in result['tests'])
            result['status']='REGRESSIONS_PASS' if result['accepted'] else 'REGRESSION_UNPROVEN' if any(t['status']=='UNPROVEN' for t in result['tests']) else 'REGRESSION_FAILED'
    except RuntimeError as exc:result.update(status='SETUP_ERROR',error=str(exc))
    except (OSError,ValueError,KeyError,TypeError) as exc:result['error']=str(exc)
    return result


def main():
    p=argparse.ArgumentParser(description='Recheck exported FIFO regressions without RTLRefine or an API key')
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent.parent);p.add_argument('--report',type=Path)
    args=p.parse_args();result=run_suite(args.root);text=json.dumps(result,indent=2)
    if args.report:args.report.write_text(text+'\n')
    print(text)
    return 0 if result['accepted'] else 1 if result['status']=='REGRESSION_FAILED' else 2


if __name__=='__main__':raise SystemExit(main())
