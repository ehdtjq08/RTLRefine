import itertools
import json

import pytest

from rtl_agent.evidence_ranking.features import dependency_evidence,build_cards
from rtl_agent.evidence_ranking.aggregate import consensus,exact_random_baseline
from rtl_agent.evidence_ranking.model import parse


def test_dependency_backtracks_data_state_edges_but_not_clock():
    module={'ports':{'out':{'bits':[3]}},'cells':{
        'ff':{'type':'$dff','port_directions':{'D':'input','CLK':'input','Q':'output'},'connections':{'D':[2],'CLK':[9],'Q':[3]},'attributes':{'src':'candidate.v:10.1-12.1'}},
        'comb':{'type':'$not','port_directions':{'A':'input','Y':'output'},'connections':{'A':[1],'Y':[2]},'attributes':{'src':'candidate.v:5.1-5.9'}},
        'clock':{'type':'$not','port_directions':{'A':'input','Y':'output'},'connections':{'A':[8],'Y':[9]},'attributes':{'src':'candidate.v:99.1-99.9'}}}}
    evidence=dependency_evidence(module,{'port':'out','cycle':7,'expected':1,'actual':0})
    assert any(e['first_line']==5 and e['state_edges']==1 for e in evidence)
    assert not any(e['first_line']==99 for e in evidence)


def test_reset_bundle_structural_coverage_tracks_assignments_not_insertion_span():
    source='module m();\nend\n';point=source.index('end')
    def item(key,text):return {'id':key,'family':'reset_completion','line':2,'note':'reset','edits':[{'start':point,'end':point,'old':'','replacement':text}],'rtl_sha256':key*64}
    pool=[item('a','a<=0;'),item('b','b<=0;'),item('c','a<=0; b<=0;')]
    cards=build_cards(source,pool,{'ports':{},'cells':{}},[])
    assert cards[0]['structural_coverage']['fraction']==.5
    assert cards[2]['structural_coverage']['fraction']==1
    assert cards[2]['structural_coverage']['edited_sites']==2


def test_stability_is_order_observation_not_fake_correctness_confidence():
    cards=[{'id':str(i),'heuristic_score':-i,'rtl_sha256':str(i)} for i in range(20)]
    result=consensus(cards,[{'status':'VALID','ids':[str(i) for i in range(8)]},{'status':'VALID','ids':[str(i) for i in range(12,20)]}])
    assert result['stability']==0 and not result['used_model_order'] and result['order'][:2]==['0','1']
    stable=consensus(cards,[{'status':'VALID','ids':['4','2']},{'status':'VALID','ids':['2','4']},{'status':'VALID','ids':['4','2']}])
    assert stable['used_model_order'] and stable['order'][0]=='4'
    assert 'probability' in stable['stability_definition']


def test_exact_random_matches_all_permutations_including_audit_trap():
    values=[{'discovery_pass':True,'accepted':True},{'discovery_pass':True,'accepted':False},{'discovery_pass':False,'accepted':False},{'discovery_pass':False,'accepted':False}]
    wins=0;rejected=0;checks=0
    for order in itertools.permutations(values):
        for i,row in enumerate(order[:2],1):
            checks+=1
            if row['discovery_pass']:
                wins+=row['accepted'];rejected+=not row['accepted'];break
    result=exact_random_baseline(values,2);n=24
    assert result['accepted_probability']==pytest.approx(wins/n)
    assert result['audit_rejection_probability']==pytest.approx(rejected/n)
    assert result['expected_candidate_checks']==pytest.approx(checks/n)


def test_model_citation_must_match_existing_patch_line_and_observed_port():
    cards=[{'id':'patch_a','line':10}]
    def response(line):return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'ranking':[{'id':'patch_a','failure_port':'out','source_line':line,'mechanism':'candidate explanation'}],'explanation':'test'})}}]}
    assert parse(response(10),cards,['out'])['ranking'][0]['id']=='patch_a'
    with pytest.raises(ValueError,match='citation'):parse(response(11),cards,['out'])


def test_operational_ids_cannot_override_machine_provenance():
    from rtl_agent.evidence_ranking.model_ids import parse as parse_ids,recover_id_order_only
    cards=[{'id':'patch_a','line':10}]
    def response(value):return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]}
    valid={'ranking':[{'id':'patch_a','mechanism':'unverified hypothesis'}],'explanation':'test'}
    assert parse_ids(response(valid),cards,[])['ranking'][0]['id']=='patch_a'
    with pytest.raises(ValueError):parse_ids(response({**valid,'source_line':999}),cards,[])
    with pytest.raises(ValueError):parse_ids(response({**valid,'ranking':[{'id':'unknown','mechanism':'x'}]}),cards,[])
    with pytest.raises(ValueError):parse_ids(response({**valid,'ranking':valid['ranking']*2}),cards,[])
    old={'ranking':[{'id':'patch_a','source_line':999,'failure_port':'invented'}]}
    assert recover_id_order_only(response(old),cards)==['patch_a']


def test_holdout_removes_only_inactive_formal_and_keeps_source_lines():
    from rtl_agent.evidence_ranking.holdout_tools import normalize_source
    text='module m();\nwire a;\n`ifdef FORMAL\n`ifdef NESTED\nassert(a);\n`endif\n`endif\nendmodule\n'
    normalized,count=normalize_source(text)
    assert normalized.count('\n')==text.count('\n') and len(normalized)==len(text)
    assert 'wire a;' in normalized and 'assert' not in normalized and 'endmodule' in normalized
    assert count==5
    with pytest.raises(ValueError):normalize_source('`ifdef FORMAL\n`else\n`endif\n')


def test_reference_capture_holds_source_payload_but_not_sink_ready():
    from rtl_agent.evidence_ranking.holdout_tools import capture_harness
    ports={n:{'direction':'input','width':1} for n in ('clk','rst','s_axis_tvalid','s_axis_tdata','m_axis_tready')}
    ports.update({n:{'direction':'output','width':1} for n in ('s_axis_tready','m_axis_tvalid','m_axis_tdata')})
    text=capture_harness(ports,'clk','m')
    names=sorted(n for n,p in ports.items() if p['direction']=='input' and n!='clk')
    assert f'input_values[{names.index("s_axis_tdata")}]=held_values' in text
    assert f'input_values[{names.index("m_axis_tready")}]=held_values' not in text
    assert 'actual_stimulus.hex' in text and 'dut.s_axis_tvalid && !dut.s_axis_tready' in text


def test_ranking_stops_at_discovery_pass_even_if_audit_rejects():
    from rtl_agent.evidence_ranking.evaluate import score_order
    labels={'trap':{'discovery_pass':True,'accepted':False},'good':{'discovery_pass':True,'accepted':True}}
    result=score_order(['trap','good'],labels)
    assert result['checks']==1 and not result['accepted']


def test_service_validates_source_provenance_and_never_calls_model_by_default(tmp_path,monkeypatch):
    from rtl_agent.common import sha256
    from rtl_agent.evidence_ranking.service import rank_existing_pool
    def forbidden(*args,**kwargs):raise AssertionError('Unexpected paid model use')
    monkeypatch.setattr('rtl_agent.evidence_ranking.service.EvidenceClient',forbidden)
    source='module m();\nwire a=0;\nendmodule\n'
    a=source.index('0');rtl=source[:a]+'1'+source[a+1:]
    patch={'id':'candidate_001','family':'test','line':2,'note':'literal change',
           'edits':[{'start':a,'end':a+1,'old':'0','replacement':'1'}],
           'rtl':rtl,'rtl_sha256':sha256(rtl.encode())}
    discovery={'traces':[{'passed':False,'first_mismatches':[]}]}
    result=rank_existing_pool({},source,'',[patch],{'ports':{},'cells':{}},discovery,tmp_path/'good')
    assert result['api_requests']==0 and not result['used_model_order']
    with pytest.raises(ValueError,match='content hash'):
        rank_existing_pool({},source,'',[{**patch,'rtl_sha256':'0'*64}],{'ports':{}},discovery,tmp_path/'bad')
    healthy=rank_existing_pool({},source,'',[],{}, {'traces':[{'passed':True}]},tmp_path/'healthy')
    assert healthy['order']==[] and healthy['api_requests']==0 and healthy['original_trace_pass']
