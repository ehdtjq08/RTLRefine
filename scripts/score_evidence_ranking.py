"""Compare frozen ranking plans to source-only heuristics and exact random."""
import argparse
import json
from pathlib import Path

from rtl_agent.common import new_run_dir,write_json
from rtl_agent.evidence_ranking.aggregate import exact_random_baseline,poisson_binomial_tail
from rtl_agent.evidence_ranking.evaluate import score_order


def fill(ids,base):return list(ids)+[i for i in base if i not in ids]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--inputs',required=True);parser.add_argument('--plans',required=True)
    parser.add_argument('--catalog',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--scope',default='Conditional ranking/randomization analysis on known development pools, not independent or universal RTL superiority. Three trials do not triple the number of cases.')
    args=parser.parse_args()
    inputs,plans,catalog=map(Path,(args.inputs,args.plans,args.catalog))
    if json.loads((plans/'complete.json').read_text())['status']!='COMPLETE' or json.loads((catalog/'complete.json').read_text())['status']!='COMPLETE':raise ValueError('Plans and evaluation catalog must both be complete')
    root=new_run_dir('ranking_score_analysis',args.output);prepared=json.loads((inputs/'manifest.json').read_text());rows=[]
    for entry in prepared['cases']:
        payload=json.loads((inputs/entry['opaque_id']/'rank_input.json').read_text());p=json.loads((plans/entry['opaque_id']/'plans.json').read_text())
        truth=json.loads((catalog/entry['opaque_id']/'catalog.json').read_text())
        if p['original_pass']:
            rows.append({'case':entry['opaque_id'],'case_id':entry['case_id'],'original_pass':True});continue
        by={c['id']:c for c in payload['cards']};outcomes={identity:truth['candidate_labels'][c['rtl_sha256']] for identity,c in by.items()}
        baselines={name:score_order(payload[name],outcomes) for name in ('source_order','size_order','heuristic_order')}
        random=exact_random_baseline(list(outcomes.values()));trials=[]
        for trial in p['trials']:
            base=payload['heuristic_order'];raw=fill(trial['raw']['ids'],base) if trial['raw']['status']=='VALID' else base
            single=fill(trial['views'][0]['ids'],base) if trial['views'][0]['status']=='VALID' else base
            methods={'raw_model':score_order(raw,outcomes),'evidence_single':score_order(single,outcomes),'evidence_consensus':score_order(trial['consensus']['order'],outcomes)}
            trials.append({'trial':trial['trial'],'methods':methods,'stability':trial['consensus']['stability'],'used_model_order':trial['consensus']['used_model_order']})
        rows.append({'case':entry['opaque_id'],'case_id':entry['case_id'],'original_pass':False,'baselines':baselines,'exact_random':random,'trials':trials})
    real=[r for r in rows if not r['original_pass']];totals={}
    for method in ('source_order','size_order','heuristic_order'):
        totals[method]={'accepted_cases':sum(r['baselines'][method]['accepted'] for r in real),'cases':len(real),'checks':sum(r['baselines'][method]['checks'] for r in real)}
    for method in ('raw_model','evidence_single','evidence_consensus'):
        rates=[sum(r['trials'][i]['methods'][method]['accepted'] for r in real) for i in range(len(real[0]['trials']))]
        totals[method]={'accepted_per_trial':rates,'mean_accepted_cases':sum(rates)/len(rates),'cases':len(real)}
    random_probs=[r['exact_random']['accepted_probability'] for r in real]
    report={'status':'COMPLETE','cases':rows,'totals':totals,'exact_random_expected_accepted_cases':sum(random_probs),
            'randomization_tails_for_consensus_trials':[poisson_binomial_tail(random_probs,v) for v in totals['evidence_consensus']['accepted_per_trial']],
            'scope':args.scope,
            'no_candidate_outcome_in_model_context':True}
    write_json(root/'summary.json',report);print(json.dumps({k:report[k] for k in ('totals','exact_random_expected_accepted_cases')},indent=2))


if __name__=='__main__':main()
