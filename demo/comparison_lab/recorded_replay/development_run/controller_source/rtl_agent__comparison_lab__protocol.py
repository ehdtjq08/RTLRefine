"""Freeze comparisons and all implementation inputs before collecting plans."""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime,timezone

from ..common import ROOT,sha256,write_json
from .data import load_public,verify_bundle,digest,canonical_project
from .policies import METHODS

DEFAULT_BASELINES=['size_order','heuristic_order','size_circuit_rrf','raw_single','raw_consensus']


def register_study(manifest_file,output,*,development_bundle,trials=3,candidate=None,candidate_views='evidence',overrides=None):
    """Register policy before native preparation reads any source/trace file."""
    manifest_file=Path(manifest_file).resolve();spec=json.loads(manifest_file.read_text())
    _,development=load_public(development_bundle)
    groups={canonical_project(c['project']) for c in spec['cases']};dev_groups={c['project'] for c in development['cases'].values()}
    defect_groups={canonical_project(c['project']) for c in spec['cases'] if c['kind']!='normal_control'}
    if spec['exposure']!='unexamined':raise ValueError('Final study sources must be unexamined by algorithm development')
    if groups & dev_groups:raise ValueError('Final projects overlap development')
    if len(defect_groups)<8 or trials<3:raise ValueError('Register at least eight independent defect projects and three trials')
    hashes=implementation_hashes();relative=None
    if candidate:
        candidate=Path(candidate).resolve()
        if not candidate.is_relative_to(ROOT):raise ValueError('Policy must be inside the project')
        relative=str(candidate.relative_to(ROOT));hashes[relative]=sha256(candidate.read_bytes())
    registration={'schema_version':1,'registered_at':datetime.now(timezone.utc).isoformat(),
        'source_manifest_sha256':sha256(manifest_file.read_bytes()),'development_bundle_seal':verify_bundle(development_bundle),
        'development_projects':sorted(dev_groups),'projects':sorted(groups),'code_hashes':hashes,
        'trials':trials,'candidate_policy':relative,'candidate_views':candidate_views,'overrides':overrides or {},
        'source_and_trace_contents_read_during_registration':False}
    path=Path(output)
    if path.exists():raise FileExistsError(path)
    from .exposure import reserve
    reserve(groups,digest(registration),state='registered')
    path.parent.mkdir(parents=True,exist_ok=True);write_json(path,registration)
    return registration


def verify_study(registration):
    for relative,expected in registration['code_hashes'].items():
        if sha256((ROOT/relative).read_bytes())!=expected:raise ValueError('Policy changed after study registration: '+relative)
    return registration


def implementation_hashes():
    paths=list(Path(__file__).parent.glob('*.py'))
    paths += [ROOT/n for n in ('rtl_agent/evidence_ranking/aggregate.py','rtl_agent/evidence_ranking/features.py',
        'rtl_agent/evidence_ranking/model_ids.py','rtl_agent/evidence_ranking/model.py','rtl_agent/model_client.py',
        'rtl_agent/budget.py','rtl_agent/model_settings.py','configs/pricing.json','configs/budget.json',
        'rtl_agent/known_bugs_v2/engine.py','rtl_agent/known_bugs_v2/cases.py','rtl_agent/known_bugs_v2/runner.py',
        'rtl_agent/known_bugs_v2/evaluator.py','rtl_agent/repair_search/candidates.py','rtl_agent/repair_search/retention.py',
        'rtl_agent/tool_runner.py','rtl_agent/tool_paths.py','rtl_agent/common.py')]
    return {str(p.relative_to(ROOT)):sha256(p.read_bytes()) for p in sorted(paths)}


def freeze(bundle,run,*,mode='development',provider='recorded',trials=1,development_bundle=None,overrides=None,candidate=None,candidate_views='evidence'):
    packets,meta=load_public(bundle);run=Path(run);bundle=Path(bundle).resolve()
    if mode not in ('development','confirmatory'):raise ValueError('Invalid evaluation mode')
    if provider not in ('recorded','live'):raise ValueError('Invalid provider')
    if isinstance(trials,bool) or not 1<=trials<=10:raise ValueError('Use one to ten predeclared trials')
    if provider=='recorded' and trials!=1:raise ValueError('Recorded views cannot be replicated as new trials')
    groups={m['project'] for m in meta['cases'].values()}
    defect_groups={m['project'] for m in meta['cases'].values() if m['kind']!='normal_control'}
    development_groups=set()
    if development_bundle:
        _,dev=load_public(development_bundle);development_groups={m['project'] for m in dev['cases'].values()}
    if mode=='confirmatory':
        if provider!='live':raise ValueError('Confirmatory inference must be collected prospectively')
        if not development_bundle:raise ValueError('A development dataset is required to audit the project split')
        if meta.get('exposure')!='unexamined' or any(c.get('exposure')!='unexamined' for c in meta['cases'].values()):
            raise ValueError('Previously examined cases cannot become final test cases')
        if groups & development_groups:raise ValueError('Upstream project overlaps development and final evaluation')
        if (bundle/'OUTCOMES_OPENED.json').exists():raise ValueError('Final labels have already been opened')
        registration=meta.get('study_registration')
        if not registration or not meta.get('preparation_checked_registered_policy'):raise ValueError('Final native data preparation must follow a registered study')
        verify_study(registration)
        if registration['trials']!=trials or registration['candidate_policy']!=(str(Path(candidate).resolve().relative_to(ROOT)) if candidate else None) or registration['candidate_views']!=candidate_views or registration['overrides']!=(overrides or {}):
            raise ValueError('Final settings differ from the pre-preparation registration')
        if registration['development_bundle_seal']!=verify_bundle(development_bundle):raise ValueError('Registered development cohort changed')
    protocol={'schema_version':1,'bundle':str(bundle),'bundle_seal':verify_bundle(bundle),'mode':mode,'provider':provider,'trials':trials,
        'methods':list(METHODS)+['random_order'],'treatment':'evidence_consensus','primary_baselines':DEFAULT_BASELINES,
        'check_budgets':[1,2,4,8],'primary_metric':'normalized_trapezoid_auc_over_log2_check_budget',
        'alpha':.05,'min_practical_effect':.05,'minimum_independent_projects':8,'bootstrap_resamples':5000,
        'api_cost_ceilings_usd':[0,.01,.03,.1],'run_api_cap_usd':4.,'seed':20261023,
        'stopping':'First public-trace pass, then passive audit; never retry after audit rejection',
        'policy_error_fallback':'heuristic_order; errors retained, never excluded',
        'comparison_scope':'Matched candidate-check budgets. Model API overhead is attributed; end-to-end compute is unequal.',
        'inference_views':{'raw':3,'evidence':3},'model':'nvidia/Nemotron-3-Ultra-550b-a55b',
        'project_groups':sorted(groups),'development_project_groups':sorted(development_groups),
        'meta_sha256':sha256((bundle/'metadata.json').read_bytes()),'code_hashes':implementation_hashes()}
    if overrides:
        allowed={'check_budgets','primary_baselines','alpha','min_practical_effect','minimum_independent_projects','bootstrap_resamples','run_api_cap_usd','seed'}
        if set(overrides)-allowed:raise ValueError('Unsupported protocol override')
        protocol.update(overrides)
    if candidate:
        candidate=Path(candidate).resolve()
        if not candidate.is_relative_to(ROOT) or candidate.suffix!='.py' or candidate.stat().st_size>50000:raise ValueError('Candidate policy must be a project Python file <=50KB')
        if candidate_views not in ('none','raw','evidence','both'):raise ValueError('Invalid declared model inputs')
        relative=str(candidate.relative_to(ROOT));protocol['candidate_policy']=relative
        protocol['candidate_views']=candidate_views;protocol['code_hashes'][relative]=sha256(candidate.read_bytes())
        protocol['treatment']='candidate';protocol['methods'].append('candidate')
        if 'evidence_consensus' not in protocol['primary_baselines']:protocol['primary_baselines']=protocol['primary_baselines']+['evidence_consensus']
    if type(protocol['bootstrap_resamples']) is not int or type(protocol['minimum_independent_projects']) is not int or type(protocol['seed']) is not int:raise ValueError('Counts and seed must be integers')
    if not 0<protocol['alpha']<=.05 or protocol['bootstrap_resamples']<100:raise ValueError('Invalid statistical configuration')
    if not 0<protocol['min_practical_effect']<=1 or not 0<protocol['run_api_cap_usd']<=50:raise ValueError('Invalid effect or budget cap')
    if mode=='confirmatory':
        if protocol['minimum_independent_projects']<8 or trials<3:raise ValueError('Final comparison needs at least eight projects and three trials per case')
        if len(defect_groups)<protocol['minimum_independent_projects']:raise ValueError('Insufficient independent defect projects before collection')
        if not set(DEFAULT_BASELINES)<=set(protocol['primary_baselines']):raise ValueError('Final comparison cannot omit strong default baselines')
        if protocol['bootstrap_resamples']<5000:raise ValueError('Final comparison needs the registered resampling precision')
    if protocol['check_budgets']!=sorted(set(protocol['check_budgets'])) or any(type(b) is not int or b<1 or b>8 for b in protocol['check_budgets']):raise ValueError('Use increasing integer check budgets from one to eight')
    if len(protocol['check_budgets'])<2:raise ValueError('A budget curve needs at least two points')
    if len(set(protocol['primary_baselines']))!=len(protocol['primary_baselines']) or not set(protocol['primary_baselines'])<=set(METHODS)-{protocol['treatment']} or not protocol['primary_baselines']:raise ValueError('Invalid primary baselines')
    if provider=='recorded':protocol['recorded_views_sha256']=sha256((bundle/'recorded_views.json').read_bytes())
    if mode=='confirmatory' and protocol['check_budgets']!=[1,2,4,8]:raise ValueError('Final default study keeps the full registered budget curve')
    if run.exists():raise FileExistsError(run)
    if mode=='confirmatory':
        from .exposure import reserve
        reserve(groups,digest(protocol),parent_study=digest(meta['study_registration']))
    run.mkdir(parents=True,exist_ok=False)
    write_json(run/'protocol.json',protocol);write_json(run/'PROTOCOL_SEAL.json',{'sha256':digest(protocol)})
    snapshot=run/'controller_source';snapshot.mkdir()
    for relative in protocol['code_hashes']:(snapshot/relative.replace('/','__')).write_bytes((ROOT/relative).read_bytes())
    return protocol


def load_protocol(run):
    run=Path(run);protocol=json.loads((run/'protocol.json').read_text())
    if digest(protocol)!=json.loads((run/'PROTOCOL_SEAL.json').read_text())['sha256']:raise ValueError('Protocol was modified')
    if verify_bundle(protocol['bundle'])!=protocol['bundle_seal']:raise ValueError('Dataset changed after registration')
    for relative,expected in protocol['code_hashes'].items():
        if sha256((ROOT/relative).read_bytes())!=expected:raise ValueError('Registered implementation changed: '+relative)
    if protocol['mode']=='confirmatory':
        from .exposure import verify_reservation
        verify_reservation(protocol['project_groups'],digest(protocol))
    return protocol
