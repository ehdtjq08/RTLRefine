"""Measure one compile-once prototype against independently stored discovery labels."""
import argparse
import json
from pathlib import Path

from rtl_agent.common import ROOT,write_json
from rtl_agent.known_bugs_v2.cases import DATA,load
from rtl_agent.batch_repair.engine import screen


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',default='case_11');parser.add_argument('--output',required=True);args=parser.parse_args()
    manifest=json.loads((ROOT/'results/repair_search_pools_v1_20261023/manifest.json').read_text())
    entry=next(e for e in manifest['cases'] if e['opaque_id']==args.case);case=load(entry['case_id']);base=DATA/case['id']
    pool=json.loads((ROOT/'results/repair_search_pools_v1_20261023'/args.case/'pool.json').read_text())
    trace={**case['traces'][0],'stimulus':str(base/case['traces'][0]['stimulus']),'expected':str(base/case['traces'][0]['expected'])}
    result=screen((base/'input.v').read_text(),(base/'dependencies.v').read_text(),case,pool,trace,args.output)
    truth=json.loads((ROOT/'results/evidence_private_catalog_v1_20261023'/args.case/'catalog.json').read_text())['candidate_labels']
    by={c['id']:c for c in pool};discrepancies=[]
    for identity,r in result['results'].items():
        if r['passed']!=truth[by[identity]['rtl_sha256']]['discovery_pass']:discrepancies.append(identity)
    report={'status':result['status'],'screened':len(result['results']),'fallback':len(result['fallback_ids']),
            'wall_seconds':result['wall_seconds'],'inactive_control_match':result.get('inactive_selector_exact_output_match'),
            'standalone_discovery_discrepancies':discrepancies,'new_model_calls':0}
    write_json(Path(args.output)/'probe_summary.json',report);print(json.dumps(report,indent=2))


if __name__=='__main__':main()
