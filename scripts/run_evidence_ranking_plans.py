"""Freeze ranking policy, then collect source-only plans without outcome access."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path
import random
import threading
import time

from rtl_agent.budget import BudgetLedger
from rtl_agent.common import ROOT,new_run_dir,sha256,write_json
from rtl_agent.known_bugs_v2.cases import DATA,load
from rtl_agent.evidence_ranking.model import EvidenceClient,MODEL,MAX_TOKENS,SETTINGS,messages,parse
from rtl_agent.evidence_ranking.aggregate import consensus


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--inputs',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--trials',type=int,choices=(1,3),default=3);args=parser.parse_args()
    inputs=Path(args.inputs).resolve();prepared=json.loads((inputs/'manifest.json').read_text())
    for n,h in prepared['algorithm_hashes'].items():
        if sha256((ROOT/n).read_bytes())!=h:raise ValueError('Ranking algorithm changed after preparation')
    root=new_run_dir('evidence_ranking_plans',args.output);snapshot=root/'algorithm_source';snapshot.mkdir()
    files=list((ROOT/'rtl_agent/evidence_ranking').glob('*.py'))+[Path(__file__).resolve(),ROOT/'scripts/prepare_evidence_ranking.py',ROOT/'scripts/build_candidate_catalog.py']
    files += [ROOT/n for n in ('rtl_agent/model_client.py','rtl_agent/model_settings.py','rtl_agent/budget.py','configs/budget.json','configs/pricing.json')]
    hashes={}
    for f in files:
        name=str(f.relative_to(ROOT));data=f.read_bytes();(snapshot/name.replace('/','__')).write_bytes(data);hashes[name]=sha256(data)
    protocol={'trials':args.trials,'views_per_evidence_trial':3,'raw_views_per_trial':1,'same_candidate_cap':8,'forced_prefix':0,
              'evidence_features':'Original static dependency overapproximation, direct changed targets, related-site scope completeness, edit size',
              'heuristic_weights':{'dependency_relevance':4,'structural_completeness':2,'minimality':.5,'direct_failure_target':2},
              'consensus':'Top-eight Borda; content-hash tie break with fixed heuristic; below .35 mean top-eight Jaccard falls back to heuristic',
              'confidence_limit':'Stability and citation validity are not correctness probabilities or causal proof',
              'model':MODEL,'settings':SETTINGS.to_dict(),'max_output_tokens':MAX_TOKENS,'estimated_spend_cap':6.,
              'candidate_outcomes_available_to_ranker':False,'private_catalog_may_be_scored_only_after_all_plans':True,
              'inputs_manifest_sha256':sha256((inputs/'manifest.json').read_bytes()),'algorithm_hashes':hashes,
              'scope':'Known development cohort; this run cannot establish unseen-module or general RTL superiority.'}
    write_json(root/'protocol.json',protocol);ledger=BudgetLedger();write_json(root/'budget_before.json',ledger.summary())
    EvidenceClient(['catalog_check'],['out']).verify_model()
    condition=threading.Condition();active=[0];paid=[];maximum=ledger.quote(MODEL,MAX_TOKENS)['reserved_usd']
    def reserve():
        with condition:
            while True:
                spent=sum((p['cost'].get('estimated_usd') if p['cost'].get('estimated_usd') is not None else p['cost']['reserved_usd']) for p in paid if p['cost'])
                if spent+maximum*(active[0]+1)<=6.:active[0]+=1;return
                if not active[0]:raise RuntimeError('Prespecified ranking spend cap exhausted')
                condition.wait(timeout=1)
    def call(case,source,deps,cards,discovery,folder,include_evidence):
        folder.mkdir();ports=sorted({m['port'] for m in discovery['traces'][0]['first_mismatches']});ids=[c['id'] for c in cards]
        prompt=messages(case,source,deps,cards,discovery,include_evidence=include_evidence)
        encoded=json.dumps(prompt)
        if any(token in encoded for token in ('private_candidate_catalog','candidate_labels','audit_pass','control_sources','trace_1/','trace_2/')):raise ValueError('Outcome leakage')
        write_json(folder/'messages.json',prompt);reserve();client=EvidenceClient(ids,ports);before=client.inference_requests;start=time.monotonic()
        result={'status':'ERROR','ids':[]}
        try:
            response=client.generate(prompt,max_tokens=MAX_TOKENS);write_json(folder/'response.json',response)
            value=parse(response,cards,ports);write_json(folder/'proposal.json',value);result.update({'status':'VALID','ids':[v['id'] for v in value['ranking']],'proposal':value})
        except Exception as exc:result['error']=client.redact(type(exc).__name__+': '+str(exc))
        finally:
            result.update({'api_requests':client.inference_requests-before,'cost':client.last_cost,'wall_seconds':round(time.monotonic()-start,4)})
            with condition:
                if result['api_requests']:paid.append({'path':str(folder.relative_to(root)),'cost':result['cost'],'requests':result['api_requests']})
                active[0]-=1;write_json(root/'paid_requests.json',paid);condition.notify_all()
        write_json(folder/'ranking.json',result);return result
    def worker(entry):
        path=inputs/entry['opaque_id']/'rank_input.json'
        if sha256(path.read_bytes())!=entry['rank_input_sha256']:raise ValueError('Prepared input changed')
        payload=json.loads(path.read_text());folder=root/entry['opaque_id'];folder.mkdir();case=load(entry['case_id'])
        if payload['original_discovery_pass']:
            write_json(folder/'plans.json',{'original_pass':True,'trials':[]});return
        source=(DATA/case['id']/'input.v').read_text();deps=(DATA/case['id']/'dependencies.v').read_text();cards=payload['cards'];trials=[]
        for trial in range(args.trials):
            current=folder/f'trial_{trial+1}';current.mkdir();views=[]
            for view in range(3):
                shuffled=sorted(cards,key=lambda c:c['id']);random.Random(20261023+trial*997+view*17+int(entry['opaque_id'].split('_')[-1])*31).shuffle(shuffled)
                if view==0:raw=call(case,source,deps,shuffled,payload['original_discovery'],current/'raw_no_features',False)
                views.append(call(case,source,deps,shuffled,payload['original_discovery'],current/f'evidence_view_{view+1}',True))
            aggregated=consensus(cards,views);row={'trial':trial+1,'raw':raw,'views':views,'consensus':aggregated};trials.append(row)
            write_json(folder/'plans.json',{'original_pass':False,'trials':trials})
            print({'planned':entry['opaque_id'],'trial':trial+1,'stability':aggregated['stability'],'used_model':aggregated['used_model_order']},flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(worker,e) for e in prepared['cases']]
        for f in as_completed(futures):f.result()
    for n,h in hashes.items():
        if sha256((ROOT/n).read_bytes())!=h:raise ValueError('Ranking algorithm changed during collection')
    write_json(root/'complete.json',{'status':'COMPLETE','rankings_frozen_before_outcome_analysis':True,'calls':sum(p['requests'] for p in paid),
               'estimated_cost':sum((p['cost'] or {}).get('estimated_usd') or 0 for p in paid)})
    write_json(root/'budget_after.json',ledger.summary())


if __name__=='__main__':main()
