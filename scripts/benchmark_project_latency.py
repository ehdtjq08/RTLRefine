"""Paired no-inference pipeline timings against an immutable source checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parent.parent
CASES=('axis-register','wide-math','dual-clock','uart-peer')


def decision(row):
    return {k:row.get(k) for k in ['id','phase','passed','checks','status','interface']}


def worker(source,archive,output):
    sys.path.insert(0,str(source))
    from rtl_agent.project_repair.project import read_archive,load_project
    from rtl_agent.project_repair.workflow import run_project
    result=run_project(load_project(read_archive(archive.read_bytes())),output=str(output))
    assert result['accepted'] and result['api_requests']==0
    checks=[*result['baseline']['tests'],*result['final_check']['tests']]
    commands=[c for t in checks for c in t['commands']]
    h=hashlib.sha256()
    with zipfile.ZipFile(output/'checked-project.zip') as z:
        for name in sorted(z.namelist()):
            data=z.read(name);h.update(name.encode()+b'\0'+hashlib.sha256(data).digest())
    record={'pipeline_seconds':result['wall_seconds'],'standalone_ci_seconds':result['ci_regressions']['wall_seconds'],
            'application_native_command_seconds':sum(c['wall_seconds'] for c in commands),'cache_hits':sum(c.get('cache_hit',False) for c in commands),
            'recorded_native_commands':len(commands),'executed_native_commands':sum(not c.get('cache_hit',False) for c in commands),
            'new_model_calls':result['api_requests'],'export_payload_sha256':h.hexdigest(),
            'decision':{'accepted':result['accepted'],'status':result['status'],'design_hashes':result['selected_design_hashes'],
                        'public':[decision(t) for t in result['baseline']['tests']],
                        'final':[decision(t) for t in result['final_check']['tests']],
                        'ci':[decision(t) for t in result['ci_regressions']['tests']]}}
    (output/'timing.json').write_text(json.dumps(record,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--reference-source');p.add_argument('--output');p.add_argument('--trials',type=int,default=4)
    p.add_argument('--worker-source');p.add_argument('--input-archive');p.add_argument('--worker-output');a=p.parse_args()
    if a.worker_source:
        worker(Path(a.worker_source).resolve(),Path(a.input_archive).resolve(),Path(a.worker_output).resolve());return
    if not a.reference_source or not a.output or not 2<=a.trials<=8:p.error('Provide --reference-source and --output; use 2–8 paired trials')
    out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False);reference=Path(a.reference_source).resolve()
    plan={'cases':CASES,'paired_trials':a.trials,'order':'reference/optimized on even trials, reversed on odd trials',
          'includes':'public check, all final tests, exact exported standalone gate and packaging','fresh_work_directories':True,
          'native_parallelism':1,'new_model_calls':0,'scope':'Four existing exposed fixtures on one host; not model latency or general RTL speed.'}
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');rows=[]
    env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'LANG':'C','LC_ALL':'C','RTLREFINE_ENABLE_LIVE_MODEL':'0'}
    for case in CASES:
        expected=None;payload=None;archive=ROOT/'demo/general_project_ci'/case/'checked-project.zip'
        for trial in range(a.trials):
            modes=('reference','optimized') if trial%2==0 else ('optimized','reference')
            for mode in modes:
                folder=out/f'{case}-{trial}-{mode}';source=reference if mode=='reference' else ROOT;started=time.perf_counter()
                subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--worker-source',str(source),
                    '--input-archive',str(archive),'--worker-output',str(folder)],env=env,check=True,stdout=subprocess.DEVNULL,timeout=200)
                r=json.loads((folder/'timing.json').read_text());r['cli_seconds']=time.perf_counter()-started
                if expected is None:expected=r['decision'];payload=r['export_payload_sha256']
                assert r['decision']==expected and r['export_payload_sha256']==payload,(case,mode)
                row={k:v for k,v in r.items() if k!='decision'};row.update(case=case,trial=trial,mode=mode,same_decisions_and_export_payload=True);rows.append(row)
                print(json.dumps({k:row[k] for k in ['case','trial','mode','pipeline_seconds','cache_hits','executed_native_commands']}),flush=True)
    summary=[]
    for case in CASES:
        left=[r for r in rows if r['case']==case and r['mode']=='reference'];right=[r for r in rows if r['case']==case and r['mode']=='optimized']
        x=statistics.median(r['pipeline_seconds'] for r in left);y=statistics.median(r['pipeline_seconds'] for r in right)
        summary.append({'case':case,'reference_median_seconds':x,'optimized_median_seconds':y,'speed_ratio':x/y,
                        'elapsed_reduction_percent':100*(1-y/x),'all_decisions_and_export_payloads_equal':True})
    report={'status':'PASS','plan':plan,'python':sys.version.split()[0],'platform':platform.platform(),
            'cpu_affinity_count':len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else os.cpu_count(),
            'rows':rows,'summary':summary,'new_model_calls':0}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
