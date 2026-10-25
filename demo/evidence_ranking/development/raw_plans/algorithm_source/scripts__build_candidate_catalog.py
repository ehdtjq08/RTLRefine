"""Complete private candidate labels for exact random baselines; no model input."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path

from rtl_agent.common import ROOT,new_run_dir,sha256,write_json
from rtl_agent.known_bugs_v2.cases import DATA,load
from rtl_agent.repair_search.execution import discover,audit


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--inputs',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    inputs=Path(args.inputs).resolve();prepared=json.loads((inputs/'manifest.json').read_text())
    for n,h in prepared['algorithm_hashes'].items():
        if sha256((ROOT/n).read_bytes())!=h:raise ValueError('Algorithm changed after feature preparation')
    root=new_run_dir('private_candidate_catalog',args.output)
    write_json(root/'protocol.json',{'rank_input_manifest_sha256':sha256((inputs/'manifest.json').read_bytes()),'model_access_allowed':False,
               'candidate_outcomes_not_used_for_ranking':'All candidate scores are evaluation labels only; rankers must finish before these are read.',
               'frozen_source_hashes':prepared['algorithm_hashes']})
    pools=ROOT/'results/repair_search_pools_v1_20261023';old=ROOT/'results/repair_search_comparison_v1_20261023'
    def worker(entry):
        case=load(entry['case_id']);folder=root/entry['opaque_id'];folder.mkdir()
        candidates=json.loads((pools/entry['opaque_id']/'pool.json').read_text());rows={};physical=0;reused=0
        payload=json.loads((inputs/entry['opaque_id']/'rank_input.json').read_text())
        if payload['original_discovery_pass']:
            write_json(folder/'catalog.json',{'original_pass':True,'candidate_labels':{}});return
        for c in candidates:
            previous=old/entry['opaque_id']/c['id'];saved=previous/'discovery.json'
            if saved.exists():
                result=json.loads(saved.read_text());reused+=1
                if result['rtl_sha256']!=c['rtl_sha256']:raise ValueError('Cached candidate mismatch')
                if result['discovery_pass']:
                    if (previous/'evaluation.json').exists():result=json.loads((previous/'evaluation.json').read_text())
                    else:
                        # This candidate's immutable compiled model is copied to a new
                        # directory before auditing; never overwrite an old run.
                        import shutil
                        copy=folder/(c['id']+'_cached');shutil.copytree(previous,copy)
                        result={**result,'directory':str(copy)};result=audit(case['id'],result)
            else:
                result=discover(case['id'],c['rtl'],folder/c['id']);physical+=1
                if result['discovery_pass']:result=audit(case['id'],result)
            rows[c['rtl_sha256']]={'discovery_pass':result['discovery_pass'],'accepted':bool(result.get('accepted')),
                                  'status':result['status'],'legacy_id':c['id'],'result_directory':result.get('directory',str(previous))}
            write_json(folder/'catalog.json',{'original_pass':False,'candidate_labels':rows,'new_discoveries':physical,'reused':reused})
        print({'catalog_case':entry['opaque_id'],'labels':len(rows),'new_checks':physical,'reused':reused},flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(worker,e) for e in prepared['cases']]
        for f in as_completed(futures):f.result()
    for n,h in prepared['algorithm_hashes'].items():
        if sha256((ROOT/n).read_bytes())!=h:raise ValueError('Algorithm changed during catalog evaluation')
    write_json(root/'complete.json',{'status':'COMPLETE','cases':len(prepared['cases']),'new_model_calls':0})


if __name__=='__main__':main()
