"""Pre-outcome amendment: ignore model citations and retain only verified IDs."""
import argparse
import json
from pathlib import Path

from rtl_agent.common import ROOT,new_run_dir,sha256,write_json
from rtl_agent.evidence_ranking.model_ids import recover_id_order_only
from rtl_agent.evidence_ranking.aggregate import consensus


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--inputs',required=True);parser.add_argument('--plans',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    inputs,plans=Path(args.inputs),Path(args.plans)
    if not (plans/'complete.json').exists():raise ValueError('Do not reinterpret a running collection')
    root=new_run_dir('machine_anchor_amendment',args.output);prepared=json.loads((inputs/'manifest.json').read_text())
    write_json(root/'AMENDMENT_BEFORE_OUTCOME_ANALYSIS.json',{'reason':'Model source citations frequently fail validation. Machine facts must not be delegated to model prose.',
               'selection':'Keep existing unique IDs from first eight raw ranked items; ignore source/port claims; no new model requests or candidate outcomes used',
               'original_strict_results_preserved':True,'prospectively_registered_before_original_inference':False,
               'amendment_script_sha256':sha256(Path(__file__).read_bytes()),'model_ids_sha256':sha256((ROOT/'rtl_agent/evidence_ranking/model_ids.py').read_bytes())})
    for entry in prepared['cases']:
        payload=json.loads((inputs/entry['opaque_id']/'rank_input.json').read_text());old=json.loads((plans/entry['opaque_id']/'plans.json').read_text())
        folder=root/entry['opaque_id'];folder.mkdir()
        if old['original_pass']:write_json(folder/'plans.json',old);continue
        trials=[]
        def normalized(path):
            try:
                response=json.loads(path.read_text());return {'status':'VALID','ids':recover_id_order_only(response,payload['cards'])}
            except Exception as exc:return {'status':'ERROR','ids':[],'error':str(exc)}
        for row in old['trials']:
            current=plans/entry['opaque_id']/f"trial_{row['trial']}"
            raw=normalized(current/'raw_no_features/response.json')
            views=[normalized(current/f'evidence_view_{i+1}/response.json') for i in range(3)]
            trials.append({'trial':row['trial'],'raw':raw,'views':views,'consensus':consensus(payload['cards'],views)})
        write_json(folder/'plans.json',{'original_pass':False,'trials':trials})
    write_json(root/'complete.json',{'status':'COMPLETE','new_model_calls':0,'amended_interpretation_not_new_inference':True})


if __name__=='__main__':main()
