"""Fresh-directory, same-pool throughput comparison; no model or audit selection."""
import argparse
import json
from pathlib import Path
import time

from rtl_agent.common import ROOT,new_run_dir,sha256,write_json
from rtl_agent.batch_repair.engine import screen_all,standalone_screen
from rtl_agent.known_bugs_v2.cases import DATA,load
from rtl_agent.known_bugs_v2.runner import BenchmarkRunner


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    root=new_run_dir('batch_throughput',args.output)
    manifest=json.loads((ROOT/'results/repair_search_pools_v1_20261023/manifest.json').read_text())
    chosen=['case_11','case_05','case_07']
    files=list((ROOT/'rtl_agent/batch_repair').glob('*.py'))+[Path(__file__).resolve()]
    hashes={str(f.relative_to(ROOT)):sha256(f.read_bytes()) for f in files}
    write_json(root/'protocol.json',{'cases':chosen,'arm_order':'serial first on cases 1/3, batch first on case 2',
        'workload':'Complete identical source-generated pool on identical public discovery profile',
        'fresh_build_directories':True,'filesystem_cache_flushed':False,'trials_per_case':1,'new_model_calls':0,
        'timing_scope':'Compilation plus full public screening including batch inactive-control check and compatibility fallbacks',
        'limits':'Single shared-host timing run, no end-to-end repair-speed or general RTL superiority claim',
        'algorithm_hashes':hashes})
    rows=[];runner=BenchmarkRunner()
    ok,why=runner.probe(root/'isolation')
    if not ok:raise RuntimeError(why)
    for index,identity in enumerate(chosen):
        entry=next(e for e in manifest['cases'] if e['opaque_id']==identity);case=load(entry['case_id']);base=DATA/case['id']
        source=(base/'input.v').read_text();deps=(base/'dependencies.v').read_text()
        pool=json.loads((ROOT/'results/repair_search_pools_v1_20261023'/identity/'pool.json').read_text())
        trace={**case['traces'][0],'stimulus':str(base/case['traces'][0]['stimulus']),'expected':str(base/case['traces'][0]['expected'])}
        folder=root/identity;folder.mkdir();arms={}
        for arm in (('serial','batch') if index%2==0 else ('batch','serial')):
            print({'case':identity,'arm':arm,'candidates':len(pool)},flush=True)
            if arm=='batch':arms[arm]=screen_all(source,deps,case,pool,trace,folder/'batch',runner=runner)
            else:
                start=time.monotonic();results={};serial=folder/'serial';serial.mkdir()
                for c in pool:results[c['id']]=standalone_screen(source,deps,case,c,trace,serial/c['id'],runner)
                arms[arm]={'results':results,'wall_seconds':time.monotonic()-start}
                write_json(folder/'serial.json',arms[arm])
        differences=[]
        for c in pool:
            a,b=arms['serial']['results'][c['id']],arms['batch']['results'][c['id']]
            # A failed compile and an executable failing trace both reject the
            # screen; full mismatch parity is checked whenever both execute.
            if a['passed']!=b['passed'] or a['cycles'] and b['cycles'] and any(a[k]!=b[k] for k in ('cycles','comparisons','mismatch_count','first_mismatches')):differences.append(c['id'])
        row={'case':identity,'case_id':case['id'],'candidates':len(pool),'serial_seconds':arms['serial']['wall_seconds'],
             'batch_seconds':arms['batch']['wall_seconds'],'speedup':arms['serial']['wall_seconds']/arms['batch']['wall_seconds'],
             'batched_candidates':arms['batch']['batched_candidates'],'standalone_fallbacks':arms['batch']['standalone_fallbacks'],
             'discrepancies':differences,'inactive_control_match':arms['batch']['control_match']}
        rows.append(row);write_json(root/'summary.json',{'status':'RUNNING','cases':rows});print(row,flush=True)
    for name,expected in hashes.items():
        if sha256((ROOT/name).read_bytes())!=expected:raise ValueError('Engine changed during measurement')
    serial=sum(r['serial_seconds'] for r in rows);batch=sum(r['batch_seconds'] for r in rows)
    summary={'status':'COMPLETE','cases':rows,'total_candidates':sum(r['candidates'] for r in rows),
        'serial_seconds':serial,'batch_seconds':batch,'speedup':serial/batch,
        'all_screen_results_match':all(not r['discrepancies'] for r in rows),'new_model_calls':0,
        'scope':'Same complete finite pool; one paired fresh-build throughput measurement per case, not end-to-end repair or unbounded equivalence'}
    write_json(root/'summary.json',summary);print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
