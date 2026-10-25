import copy
import json
from pathlib import Path

import pytest

from rtl_agent.common import sha256,write_json
from rtl_agent.comparison_lab.data import create_bundle,public_packet,load_public
from rtl_agent.comparison_lab.protocol import freeze
from rtl_agent.comparison_lab.collect import collect,_live_view
from rtl_agent.comparison_lab.analyze import analyze,budget_auc
from rtl_agent.comparison_lab.statistics import holm,sign_flip,compare_projects


@pytest.fixture(autouse=True)
def isolate_exposure_registry(tmp_path,monkeypatch):
    monkeypatch.setattr('rtl_agent.comparison_lab.exposure.REGISTRY',tmp_path/'exposures.json')


def fixture_bundle(tmp_path,*,groups=2,exposure='previously_examined',empty=False,healthy=False,raw_views=3,project_prefix='fixture'):
    public=[];private={};meta={};recorded={}
    for index in range(groups):
        identity=f'task_{index}';ids=['patch_good','patch_bad'] if not empty and not healthy else []
        cards=[{'id':key,'legacy_id':key,'family':'test','line':2,'note':'test edit','edits':[],
                'rtl_sha256':sha256(key.encode()),'failure_anchors':[],'dependency':None,
                'structural_coverage':{'fraction':1,'edited_sites':1,'available_related_sites':1,'superset_ids':[]},
                'changed_targets':['out'],'direct_failure_target':True,
                'heuristic_components':{'relevance':0.,'structural_completeness':1.,'minimality':.5,'direct_failure_target':1},
                'heuristic_score':float(i)} for i,key in enumerate(ids)]
        case={'id':identity,'top':'m','clock':'clk','ports':{},'traces':[{'expected':'PRIVATE_AUDIT_CANARY'}]}
        payload={'cards':cards,'source_order':ids,'size_order':list(reversed(ids)),
                 'heuristic_order':list(reversed(ids)),'original_discovery_pass':healthy,
                 'original_discovery':{'traces':[{'passed':healthy,'cycles':8,'first_mismatches':[],
                    'audit_secret':'PRIVATE_AUDIT_CANARY'}]}}
        p=public_packet(identity,f'module m(); // fixture {index}\nendmodule\n','',case,payload);public.append(p)
        private[identity]={'labels':{key:{'discovery_pass':key=='patch_good','accepted':key=='patch_good','eda_seconds':1.} for key in ids},'original_accepted':healthy}
        meta[identity]={'project':f'{project_prefix}/project_{index}','module':'m','kind':'normal_control' if healthy else 'synthetic_injected',
            'solution_seeded':False,'exposure':exposure}
        def rows(n):return [{'status':'VALID','ids':ids,'cost':{'estimated_usd':.01},'wall_seconds':.02} for _ in range(n)]
        recorded[identity]={'raw':rows(raw_views),'evidence':rows(3)}
    bundle=tmp_path/'bundle'
    create_bundle(bundle,public,private,{'cohort':'system_validation','validation_fixture':True,'claim_scope':'fixture_only',
        'exposure':exposure,'cases':meta})
    write_json(bundle/'recorded_views.json',recorded)
    return bundle


def register(bundle,run,**kw):return freeze(bundle,run,overrides={'bootstrap_resamples':200},**kw)


def test_public_allowlist_excludes_audit_paths_and_extra_metadata(tmp_path):
    bundle=fixture_bundle(tmp_path);packets,_=load_public(bundle)
    assert 'PRIVATE_AUDIT_CANARY' not in json.dumps(packets)


def test_collector_cannot_open_private_labels_before_plans_are_sealed(tmp_path,monkeypatch):
    bundle=fixture_bundle(tmp_path);run=tmp_path/'run';register(bundle,run)
    original_bytes=Path.read_bytes;original_text=Path.read_text
    def no_bytes(path,*a,**k):
        if path.name=='private.json':raise AssertionError('Private file opened during planning')
        return original_bytes(path,*a,**k)
    def no_text(path,*a,**k):
        if path.name=='private.json':raise AssertionError('Private file opened during planning')
        return original_text(path,*a,**k)
    with monkeypatch.context() as m:
        m.setattr(Path,'read_bytes',no_bytes);m.setattr(Path,'read_text',no_text)
        result=collect(run)
        assert result['new_model_calls']==0
    assert (run/'PLANS_SEALED.json').exists()
    report=analyze(run)
    assert report['decision']['status']=='ADVANTAGE_NOT_ESTABLISHED'


def test_modified_protocol_and_postseal_order_are_rejected(tmp_path):
    bundle=fixture_bundle(tmp_path);run=tmp_path/'run';register(bundle,run);collect(run)
    plan=next((run/'plans').glob('*/trial_*/plan.json'));v=json.loads(plan.read_text());v['orders']['size_order'].reverse();write_json(plan,v)
    with pytest.raises(ValueError,match='Sealed plan'):analyze(run)
    assert not (bundle/'OUTCOMES_OPENED.json').exists()
    protocol=json.loads((run/'protocol.json').read_text());protocol['alpha']=.04;write_json(run/'protocol.json',protocol)
    with pytest.raises(ValueError,match='Protocol was modified'):collect(run)


def test_incomplete_run_cannot_open_test_outcomes(tmp_path):
    bundle=fixture_bundle(tmp_path);run=tmp_path/'run';register(bundle,run)
    with pytest.raises(ValueError,match='sealed'):analyze(run)
    assert not (bundle/'OUTCOMES_OPENED.json').exists()


def test_private_catalog_tampering_is_detected_at_scoring(tmp_path):
    bundle=fixture_bundle(tmp_path);run=tmp_path/'run';register(bundle,run);collect(run)
    v=json.loads((bundle/'private.json').read_text());v['task_0']['labels']['patch_good']['accepted']=False
    write_json(bundle/'private.json',v)
    with pytest.raises(ValueError,match='Dataset seal changed'):analyze(run)


def test_missing_three_call_baseline_stays_missing_not_a_fake_fallback(tmp_path):
    bundle=fixture_bundle(tmp_path,raw_views=1);run=tmp_path/'run';register(bundle,run);collect(run);r=analyze(run)
    assert not r['methods']['raw_consensus']['complete']
    assert 'raw_consensus' in r['missing_primary_methods']
    assert 'INCOMPLETE_PRIMARY_COMPARISON' in r['decision']['reasons']
    assert not r['decision']['statistical_gate_passes']


def test_empty_unrepairable_pools_remain_in_success_denominator(tmp_path):
    bundle=fixture_bundle(tmp_path,empty=True);run=tmp_path/'run';register(bundle,run);collect(run);r=analyze(run)
    assert r['candidate_generation_coverage']=={'covered':0,'total':2,'seeded_pool_track':False}
    assert r['methods']['heuristic_order']['required_task_trials']==2
    assert r['methods']['evidence_consensus']['failure_categories']['pool_miss']==2


def test_original_passing_controls_skip_inference(tmp_path):
    bundle=fixture_bundle(tmp_path,healthy=True);run=tmp_path/'run';register(bundle,run);collect(run);r=analyze(run)
    assert r['defect_cases']==0 and r['normal_control_cases']==2
    assert r['methods']['raw_consensus']['logical_model_calls']==0
    assert r['methods']['evidence_consensus']['healthy_controls_accepted']==2


def test_replay_is_idempotent_and_does_not_create_new_model_trials(tmp_path):
    bundle=fixture_bundle(tmp_path);run=tmp_path/'run';register(bundle,run);collect(run)
    before=(run/'PLANS_SEALED.json').read_bytes()
    assert collect(run)['new_model_calls']==0
    assert before==(run/'PLANS_SEALED.json').read_bytes()
    assert analyze(run)==analyze(run)
    with pytest.raises(ValueError,match='new trials'):freeze(bundle,tmp_path/'bad',provider='recorded',trials=3)


def test_compute_cost_of_rejected_model_views_is_still_charged(tmp_path):
    bundle=fixture_bundle(tmp_path);run=tmp_path/'run';register(bundle,run);collect(run);r=analyze(run)
    m=r['methods']['evidence_consensus']
    assert m['logical_model_calls']==6 and m['api_cost_usd_sum']==pytest.approx(.06)
    assert m['success_at_max_checks_under_accounted_api_ceiling']['0']==0


def test_budget_auc_is_area_on_log2_knots_not_best_budget_selection():
    assert budget_auc({'1':0,'2':0,'4':0,'8':1})==pytest.approx(1/6)
    assert budget_auc({'1':1,'2':1,'4':1,'8':1})==1


def test_holm_and_project_sign_flip_have_known_reference_values():
    assert holm({'a':.01,'b':.04,'c':.03})==pytest.approx({'a':.03,'b':.06,'c':.06})
    assert sign_flip([1,1,1])==.125
    assert sign_flip([0,0])==1
    assert sign_flip([1,-1])==.75


def test_null_and_known_winner_validate_the_statistical_gate_without_ai_claims():
    null={str(i):{'treatment':0.,'baseline':0.} for i in range(12)}
    winner={str(i):{'treatment':1.,'baseline':0.} for i in range(12)}
    assert not compare_projects(null,'treatment',['baseline'],resamples=200)['baseline']['passes_statistical_gate']
    result=compare_projects(winner,'treatment',['baseline'],resamples=200)['baseline']
    assert result['passes_statistical_gate'] and result['one_sided_sign_flip_p']==1/4096
    one_project={'one':{'treatment':1.,'baseline':0.}}
    assert compare_projects(one_project,'treatment',['baseline'],resamples=200)['baseline']['one_sided_sign_flip_p']==.5


def test_missing_comparisons_cannot_shrink_the_multiplicity_family():
    values={str(i):{'treatment':1.,'b':0.} for i in range(8)}
    result=compare_projects(values,'treatment',['b'],resamples=200,family_size=5)['b']
    assert result['holm_p']==5/256


def test_seen_cases_cannot_be_relabeled_as_a_final_evaluation(tmp_path):
    bundle=fixture_bundle(tmp_path)
    with pytest.raises(ValueError,match='Previously examined'):
        freeze(bundle,tmp_path/'run',mode='confirmatory',provider='live',trials=3,development_bundle=bundle)


def test_final_project_split_is_checked_before_any_paid_call(tmp_path):
    bundle=fixture_bundle(tmp_path,groups=8,exposure='unexamined')
    with pytest.raises(ValueError,match='overlaps'):
        freeze(bundle,tmp_path/'run',mode='confirmatory',provider='live',trials=3,development_bundle=bundle)


def test_unresolved_request_is_not_automatically_charged_twice(tmp_path,monkeypatch):
    bundle=fixture_bundle(tmp_path,groups=1);packet=load_public(bundle)[0][0];folder=tmp_path/'request';folder.mkdir()
    calls=[]
    class Ledger:
        def quote(self,*a):return {'reserved_usd':.01}
    class Client:
        def __init__(self,*a):pass
        def generate(self,*a,**k):calls.append(1);raise KeyboardInterrupt('process interrupted after dispatch')
    monkeypatch.setattr('rtl_agent.comparison_lab.collect.BudgetLedger',Ledger)
    monkeypatch.setattr('rtl_agent.comparison_lab.collect.EvidenceClient',Client)
    protocol={'model':'test','run_api_cap_usd':1}
    with pytest.raises(KeyboardInterrupt):_live_view(packet,'raw',packet['cards'],folder,protocol,tmp_path)
    with pytest.raises(ValueError,match='no automatic repeat'):_live_view(packet,'raw',packet['cards'],folder,protocol,tmp_path)
    assert len(calls)==1


def test_report_exposes_paired_losses_and_coverage(tmp_path):
    bundle=fixture_bundle(tmp_path);run=tmp_path/'run';register(bundle,run);collect(run);r=analyze(run)
    paired=r['paired_outcomes_at_max_checks']['size_order']
    assert paired['task_trial_wins']+paired['task_trial_losses']+paired['task_trial_ties']==2
    assert r['candidate_generation_coverage']['total']==2


def test_project_exposure_registry_survives_dataset_renaming(tmp_path):
    from rtl_agent.comparison_lab.exposure import opened,reserve
    opened(['upstream/project'],'old-protocol','development')
    with pytest.raises(ValueError,match='already exposed'):reserve(['upstream/project'],'new-protocol')


def test_plugin_inputs_are_declared_and_source_is_part_of_the_frozen_policy(tmp_path):
    from rtl_agent.common import ROOT
    bundle=fixture_bundle(tmp_path);run=tmp_path/'run'
    protocol=freeze(bundle,run,candidate=ROOT/'comparison_policies/reference_heuristic.py',candidate_views='none')
    assert protocol['treatment']=='candidate' and 'candidate' in protocol['methods']
    assert protocol['candidate_views']=='none'
    assert 'comparison_policies/reference_heuristic.py' in protocol['code_hashes']
    assert 'evidence_consensus' in protocol['primary_baselines']


def test_repeated_model_trials_do_not_inflate_project_sample_size(tmp_path):
    bundle=fixture_bundle(tmp_path);run=tmp_path/'run';register(bundle,run,provider='live',trials=3)
    def adapter(packet,family,menu,folder,protocol,run):
        return {'status':'VALID','ids':packet['orders']['source_order'],'cost':{'estimated_usd':0.},'wall_seconds':0.,'api_requests':0,'origin':'mock_unit_test'}
    collect(run,live_adapter=adapter);r=analyze(run)
    assert r['trials_per_case']==3 and r['defect_cases']==2 and r['independent_project_groups']==2
    assert r['methods']['evidence_consensus']['required_task_trials']==6
    assert 'TOO_FEW_INDEPENDENT_PROJECTS' in r['decision']['reasons']


def test_study_registration_does_not_read_future_rtl_or_trace_files(tmp_path):
    from rtl_agent.comparison_lab.protocol import register_study
    dev=fixture_bundle(tmp_path/'dev')
    spec=tmp_path/'future.json'
    write_json(spec,{'exposure':'unexamined','cases':[{'project':f'future/repo_{i}','kind':'synthetic_injected',
        'source':'not-fetched-yet.v'} for i in range(8)]})
    registration=register_study(spec,tmp_path/'registration.json',development_bundle=dev)
    assert registration['source_and_trace_contents_read_during_registration'] is False
    assert len(registration['projects'])==8 and not (tmp_path/'not-fetched-yet.v').exists()


def test_repository_url_aliases_cannot_bypass_exposure_audit(tmp_path):
    from rtl_agent.comparison_lab.exposure import opened,reserve
    opened(['ZipCPU/Project'],'old','development')
    with pytest.raises(ValueError,match='already exposed'):reserve(['https://github.com/zipcpu/project.git'],'new')


def test_registered_final_path_and_renamed_dataset_reuse_guard(tmp_path):
    from rtl_agent.comparison_lab.protocol import register_study
    dev=fixture_bundle(tmp_path/'dev',groups=1,project_prefix='dev')
    fixture=fixture_bundle(tmp_path/'future',groups=8,exposure='unexamined',project_prefix='future')
    public,meta=load_public(fixture);private=json.loads((fixture/'private.json').read_text())
    spec=tmp_path/'manifest.json'
    write_json(spec,{'exposure':'unexamined','cases':[{'project':m['project'],'kind':m['kind']} for m in meta['cases'].values()]})
    registration=register_study(spec,tmp_path/'study.json',development_bundle=dev,trials=3)
    # Native preparation is represented by a fixture attestation in this unit
    # test. Its metadata prevents publishing these mock responses as AI results.
    meta.update({'study_registration':registration,'preparation_checked_registered_policy':True})
    bundle=create_bundle(tmp_path/'prepared',public,private,meta);run=tmp_path/'run'
    freeze(bundle,run,mode='confirmatory',provider='live',trials=3,development_bundle=dev)
    def mock_adapter(packet,family,menu,folder,protocol,run):
        return {'status':'VALID','ids':packet['orders']['source_order'],'cost':{'estimated_usd':0.},'wall_seconds':0.,'api_requests':0,'origin':'mock_unit_test'}
    collect(run,live_adapter=mock_adapter);r=analyze(run)
    assert 'SYSTEM_VALIDATION_FIXTURE' in r['decision']['reasons']
    assert r['independent_project_groups']==8 and r['trials_per_case']==3
    renamed=create_bundle(tmp_path/'renamed',public,private,meta)
    with pytest.raises(ValueError,match='already exposed'):
        freeze(renamed,tmp_path/'second',mode='confirmatory',provider='live',trials=3,development_bundle=dev)


def test_cached_report_integrity_is_checked_before_returning_it(tmp_path):
    bundle=fixture_bundle(tmp_path);run=tmp_path/'run';register(bundle,run);collect(run);r=analyze(run)
    r['decision']['status']='FABRICATED_ADVANTAGE';write_json(run/'report.json',r)
    with pytest.raises(ValueError,match='Sealed report changed'):analyze(run)
