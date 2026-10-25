"""Original-code features only; no candidate outcome is loaded here."""
import argparse
import json
from pathlib import Path

from rtl_agent.common import ROOT,new_run_dir,sha256,write_json
from rtl_agent.known_bugs_v2.cases import DATA,load
from rtl_agent.known_bugs_v2.evaluator import feedback
from rtl_agent.known_bugs_v2.runner import BenchmarkRunner
from rtl_agent.evidence_ranking.features import build_cards,heuristic_order,size_order


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    root=new_run_dir('evidence_ranking_preparation',args.output);runner=BenchmarkRunner()
    ok,why=runner.probe(root/'probe')
    if not ok:raise RuntimeError(why)
    old=ROOT/'results/repair_search_comparison_v1_20261023';pools=ROOT/'results/repair_search_pools_v1_20261023'
    manifest=json.loads((pools/'manifest.json').read_text());rows=[]
    for entry in manifest['cases']:
        case=load(entry['case_id']);source=(DATA/case['id']/'input.v').read_text();deps=(DATA/case['id']/'dependencies.v').read_text()
        pool=json.loads((pools/entry['opaque_id']/'pool.json').read_text())
        baseline=json.loads((old/entry['opaque_id']/'original_discovery/discovery.json').read_text())
        if baseline['rtl_sha256']!=sha256(source.encode()):raise ValueError('Cached original mismatch')
        folder=root/entry['opaque_id'];folder.mkdir();(folder/'candidate.v').write_text(source);(folder/'dependencies.v').write_text(deps)
        (folder/'inspect.ys').write_text(f'read_verilog -sv candidate.v dependencies.v\nhierarchy -check -top {case["top"]}\nproc\nflatten\nmemory_collect\nwrite_json flattened.json\n')
        command=runner.run('inspect',folder,case['top'])
        if command['status']!='PASS':raise RuntimeError('Original dependency extraction failed: '+entry['opaque_id'])
        module=json.loads((folder/'flattened.json').read_text())['modules'][case['top']]
        failures=baseline['traces'][0]['first_mismatches']
        cards=build_cards(source,pool,module,failures)
        payload={'opaque_id':entry['opaque_id'],'case_id':case['id'],'source_sha256':sha256(source.encode()),'pool_sha256':sha256((pools/entry['opaque_id']/'pool.json').read_bytes()),
                 'original_discovery':feedback(baseline),'original_discovery_pass':baseline['discovery_pass'],'cards':cards,
                 'source_order':[c['id'] for c in cards],'size_order':size_order(cards),'heuristic_order':heuristic_order(cards)}
        write_json(folder/'rank_input.json',payload)
        rows.append({'opaque_id':entry['opaque_id'],'case_id':case['id'],'rank_input_sha256':sha256((folder/'rank_input.json').read_bytes()),
                     'cards':len(cards),'bounded_cone_hits':sum(c['dependency'] is not None for c in cards)})
        print(rows[-1],flush=True)
    files=sorted((ROOT/'rtl_agent/evidence_ranking').glob('*.py'))+[Path(__file__).resolve()]
    write_json(root/'manifest.json',{'cases':rows,'algorithm_hashes':{str(p.relative_to(ROOT)):sha256(p.read_bytes()) for p in files},
               'V2_data_seal':sha256((DATA/'FROZEN.json').read_bytes()),'candidate_outcomes_used':False,
               'scope':'Known development cohort. Original-source static dependency overapproximation and structural features, not dynamic causality.'})


if __name__=='__main__':main()
