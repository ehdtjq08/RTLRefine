"""Score sealed plans, keep every task, and gate claims against strong baselines."""
from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
import statistics

from ..common import write_json
from ..evidence_ranking.aggregate import exact_random_baseline
from ..evidence_ranking.evaluate import score_order
from .collect import exclusive,verify_plans,atomic_json
from .data import load_public,load_private,digest
from .statistics import compare_projects,minimum_discordant_projects


def mean(values):return statistics.mean(values) if values else None


def budget_auc(points):
    """Normalized trapezoid area at the predeclared log2(check budget) knots."""
    items=sorted((math.log2(int(k)),v) for k,v in points.items())
    width=items[-1][0]-items[0][0]
    return sum((xb-xa)*(ya+yb)/2 for (xa,ya),(xb,yb) in zip(items,items[1:]))/width


def claim_decision(protocol,metadata,comparisons,projects,missing):
    reasons=[]
    if protocol['mode']!='confirmatory':reasons.append('DEVELOPMENT_DATA')
    if metadata.get('exposure')!='unexamined':reasons.append('OUTCOMES_PREVIOUSLY_EXAMINED')
    if protocol['provider']!='live':reasons.append('RECORDED_REPLAY')
    if metadata.get('validation_fixture'):reasons.append('SYSTEM_VALIDATION_FIXTURE')
    if projects<protocol['minimum_independent_projects']:reasons.append('TOO_FEW_INDEPENDENT_PROJECTS')
    if missing:reasons.append('INCOMPLETE_PRIMARY_COMPARISON')
    complete=set(comparisons)==set(protocol['primary_baselines'])
    statistical=complete and all(c.get('passes_statistical_gate',False) for c in comparisons.values())
    if not statistical:reasons.append('NOT_BETTER_THAN_ALL_PRIMARY_BASELINES')
    return {'status':'ADVANTAGE_ESTABLISHED_FOR_REGISTERED_SCOPE' if not reasons else 'ADVANTAGE_NOT_ESTABLISHED',
        'reasons':reasons,'statistical_gate_passes':statistical,'primary_metric':protocol['primary_metric'],
        'scope':metadata['claim_scope'],'universal_rtl_superiority':False}


def analyze(run):
    run=Path(run)
    with exclusive(run):
        protocol,plans=verify_plans(run)
        if (run/'report.json').exists() and (run/'REPORT_SEAL.json').exists():
            cached=json.loads((run/'report.json').read_text())
            if digest(cached)!=json.loads((run/'REPORT_SEAL.json').read_text())['report_sha256'] or cached['protocol_sha256']!=digest(protocol):
                raise ValueError('Sealed report changed')
            return cached
        packets,meta=load_public(protocol['bundle']);by={p['id']:p for p in packets}
        # This is the first outcome decoding in the run. The marker prevents
        # reuse of this final dataset as fresh evidence under a later policy.
        bundle=Path(protocol['bundle']);marker=bundle/'OUTCOMES_OPENED.json'
        if protocol['mode']=='confirmatory' and marker.exists():
            previous=json.loads(marker.read_text())
            if previous['protocol_sha256']!=digest(protocol):raise ValueError('Final dataset already opened by another protocol')
        if not marker.exists():atomic_json(marker,{'protocol_sha256':digest(protocol),'run':str(run.resolve()),'mode':protocol['mode']})
        private=load_private(bundle);rows=[]
        from .exposure import opened
        opened(protocol['project_groups'],digest(protocol),protocol['mode'])
        for plan in plans:
            identity=plan['id'];packet=by[identity];labels=private[identity]['labels'];metadata=meta['cases'][identity]
            cover=any(x['accepted'] for x in labels.values());methods={}
            for method in protocol['methods']:
                if not plan['available'][method]:
                    methods[method]={'available':False,'reason':'Required independent inference views missing'};continue
                points={};details={}
                for cap in protocol['check_budgets']:
                    if packet['original_pass']:
                        result={'accepted':private[identity]['original_accepted'],'checks':0,'selected':None,'attempted':[],'audit_rejected':False}
                    else:result=score_order(plan['orders'][method],labels,cap)
                    points[str(cap)]=int(result['accepted']);details[str(cap)]=result
                selected=details[str(max(protocol['check_budgets']))]
                category='accepted' if selected['accepted'] else 'pool_miss' if not cover else 'audit_trap' if selected['audit_rejected'] else 'ranking_miss'
                duration=[labels[i].get('eda_seconds') for i in selected['attempted']]
                logical_eda=None if any(x is None for x in duration) else sum(duration)
                methods[method]={'available':True,'success_by_checks':points,'budget_auc':budget_auc(points),
                    'selection_at_max_budget':selected,'failure_category':category,'api_cost_usd':plan['api_cost_usd'][method],
                    'ranking_wall_seconds':plan['ranking_wall_seconds'][method],'logical_model_calls':plan['logical_model_calls'][method],
                    'logical_replay_eda_seconds':logical_eda,
                    'timing_limit':'EDA durations are shared-record serial attribution, not independently measured arm runtime.'}
            random_curve={str(k):exact_random_baseline(list(labels.values()),k)['accepted_probability'] for k in protocol['check_budgets']} if not packet['original_pass'] else {}
            rows.append({'id':identity,'trial':plan['trial'],**metadata,'pool_has_accepted_candidate':cover,
                'original_public_pass':packet['original_pass'],'methods':methods,'exact_random_curve':random_curve,'view_errors':plan['view_errors'],
                'candidate_policy_error':plan.get('candidate_policy_error')})
        defects=[r for r in rows if r['kind']!='normal_control'];controls=[r for r in rows if r['kind']=='normal_control']
        project_values={};groups=sorted({r['project'] for r in defects});method_summaries={};missing=[]
        for group in groups:
            group_rows=[r for r in defects if r['project']==group];project_values[group]={}
            for method in protocol['methods']:
                available=[r['methods'][method] for r in group_rows if r['methods'][method]['available']]
                project_values[group][method]=mean([v['budget_auc'] for v in available]) if len(available)==len(group_rows) else None
        required=[protocol['treatment']]+protocol['primary_baselines']
        for method in required:
            if any(project_values[g][method] is None for g in groups):missing.append(method)
        comparable=[b for b in protocol['primary_baselines'] if b not in missing and protocol['treatment'] not in missing]
        comparisons=compare_projects(project_values,protocol['treatment'],comparable,
            alpha=protocol['alpha'],resamples=protocol['bootstrap_resamples'],seed=protocol['seed'],min_effect=protocol['min_practical_effect'],family_size=len(protocol['primary_baselines'])) if comparable else {}
        # The correction family remains all registered baselines, even if an arm
        # is missing. Missing arms already fail the global gate; avoid presenting
        # less conservative adjusted values for a smaller opportunistic family.
        if len(comparable)!=len(protocol['primary_baselines']):
            for value in comparisons.values():value['passes_statistical_gate']=False;value['incomplete_registered_family']=True
        maximum=str(max(protocol['check_budgets']))
        for method in protocol['methods']:
            available=[r['methods'][method] for r in defects if r['methods'][method]['available']]
            available_control=[r['methods'][method] for r in controls if r['methods'][method]['available']]
            complete=len(available)==len(defects)
            points={str(k):mean([m['success_by_checks'][str(k)] for m in available]) for k in protocol['check_budgets']}
            projects=[v[method] for v in project_values.values() if v[method] is not None]
            costs=[m['api_cost_usd'] for m in available]
            cost_curves={}
            for ceiling in protocol['api_cost_ceilings_usd']:
                cost_curves[str(ceiling)]=None if any(c is None for c in costs) else mean([int(m['selection_at_max_budget']['accepted'] and m['api_cost_usd']<=ceiling+1e-12) for m in available])
            method_summaries[method]={'complete':complete,'available_task_trials':len(available),'required_task_trials':len(defects),
                'project_macro_budget_auc':mean(projects) if len(projects)==len(groups) else None,'success_by_checks':points,
                'accepted_task_trials_at_max_budget':sum(m['selection_at_max_budget']['accepted'] for m in available),
                'api_cost_usd_sum':sum(costs) if all(c is not None for c in costs) else None,
                'ranking_wall_seconds_sum':sum(m['ranking_wall_seconds'] for m in available),
                'logical_model_calls':sum(m['logical_model_calls'] for m in available),
                'success_at_max_checks_under_accounted_api_ceiling':cost_curves,
                'healthy_controls_accepted':sum(m['selection_at_max_budget']['accepted'] for m in available_control),
                'common_original_gate_not_model_health_recognition':True,
                'failure_categories':{c:sum(m['failure_category']==c for m in available) for c in ('accepted','pool_miss','audit_trap','ranking_miss')}}
        paired_at_max={}
        for baseline in protocol['primary_baselines']:
            transitions=defaultdict(int);wins=losses=ties=unavailable=0
            for row in defects:
                treatment=row['methods'][protocol['treatment']];control=row['methods'][baseline]
                if not treatment['available'] or not control['available']:unavailable+=1;continue
                a=treatment['selection_at_max_budget']['accepted'];b=control['selection_at_max_budget']['accepted']
                wins+=a and not b;losses+=b and not a;ties+=a==b
                transitions[control['failure_category']+' -> '+treatment['failure_category']]+=1
            paired_at_max[baseline]={'task_trial_wins':wins,'task_trial_losses':losses,'task_trial_ties':ties,
                'unavailable_task_trials':unavailable,'failure_transitions':dict(transitions),
                'descriptive_only':'Repeated trials are not independent statistical samples.'}
        coverage={i:r['pool_has_accepted_candidate'] for r in defects for i in [r['id']]}
        decision=claim_decision(protocol,meta,comparisons,len(groups),missing)
        report={'schema_version':1,'status':'COMPLETE','decision':decision,'cohort':meta['cohort'],
            'methods':method_summaries,'paired_primary_comparisons':comparisons,'missing_primary_methods':missing,
            'project_values':project_values,'case_rows':rows,'defect_cases':len(coverage),'normal_control_cases':len({r['id'] for r in controls}),
            'independent_project_groups':len(groups),'trials_per_case':protocol['trials'],
            'candidate_generation_coverage':{'covered':sum(coverage.values()),'total':len(coverage),'seeded_pool_track':any(c.get('solution_seeded') for c in meta['cases'].values())},
            'necessary_best_case_discordant_project_bound':minimum_discordant_projects(len(protocol['primary_baselines']),protocol['alpha']),
            'budget_matching':protocol['comparison_scope'],'statistical_limit':'Project-cluster percentile intervals are approximate. Sign-flip inference assumes exchangeability. No repeated-trial pseudoreplication.',
            'resource_limit':'Accounted API cost ceilings are secondary. Shared EDA timing is a replay attribution; no measured end-to-end speed or equal total-compute claim.',
            'candidate_policy_errors':sum(bool(r['candidate_policy_error']) for r in rows),
            'paired_outcomes_at_max_checks':paired_at_max,
            'protocol_sha256':digest(protocol),'new_model_calls_in_analysis':0}
        atomic_json(run/'report.json',report);(run/'report.md').write_text(markdown(report))
        write_json(run/'REPORT_SEAL.json',{'report_sha256':digest(report)})
        return report


def markdown(report):
    lines=['# Registered RTL comparison', '', '**'+report['decision']['status']+'**',
        '', 'Reasons: '+', '.join(report['decision']['reasons']),
        '',f"Cohort: {report['cohort']}; {report['defect_cases']} defect cases, {report['independent_project_groups']} project groups, {report['trials_per_case']} trials/case.",
        '', 'Repeated trials are averaged within projects. Missing arms and uncovered defects remain visible.', '',
        '| Method | Complete | Project-macro budget AUC | Accepted task-trials at max checks | API USD (attributed) |',
        '|---|---|---:|---:|---:|']
    for name,row in report['methods'].items():
        auc='—' if row['project_macro_budget_auc'] is None else f"{row['project_macro_budget_auc']:.4f}"
        cost='unknown' if row['api_cost_usd_sum'] is None else f"{row['api_cost_usd_sum']:.5f}"
        lines.append(f"| {name} | {row['complete']} | {auc} | {row['accepted_task_trials_at_max_budget']}/{row['required_task_trials']} | {cost} |")
    budgets=list(next(iter(report['methods'].values()))['success_by_checks'])
    lines+=['','## Full candidate-check budget curves','','| Method | '+' | '.join('Pass@'+k for k in budgets)+' |',
            '|---|'+'---:|'*len(budgets)]
    for name,row in report['methods'].items():
        values=['—' if row['success_by_checks'][k] is None else f"{row['success_by_checks'][k]:.3f}" for k in budgets]
        lines.append('| '+name+' | '+' | '.join(values)+' |')
    lines+=['','## Registered paired comparisons','','| Baseline | Effect | Simultaneous CI | Holm p | Pass |','|---|---:|---|---:|---|']
    for name,row in report['paired_primary_comparisons'].items():
        lines.append(f"| {name} | {row['effect']:.4f} | {row['familywise_percentile_ci']} | {row['holm_p']:.5f} | {row['passes_statistical_gate']} |")
    lines+=['',report['resource_limit'],'',report['statistical_limit'],'']
    lines+=['## Failure diagnosis at maximum checks','','| Baseline | Treatment-only | Baseline-only | Tied | Missing |','|---|---:|---:|---:|---:|']
    for name,row in report['paired_outcomes_at_max_checks'].items():
        lines.append(f"| {name} | {row['task_trial_wins']} | {row['task_trial_losses']} | {row['task_trial_ties']} | {row['unavailable_task_trials']} |")
    coverage=report['candidate_generation_coverage']
    lines+=['',f"Candidate coverage: {coverage['covered']}/{coverage['total']}. Seeded-pool track: {coverage['seeded_pool_track']}. Uncovered cases stay in the denominator.",'']
    return '\n'.join(lines)
