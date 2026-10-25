import json

from rtl_agent.known_bugs_v2.cases import DATA,load
from rtl_agent.repair_search.candidates import make_pool
from rtl_agent.repair_search.planner import messages,guided_order


def test_candidate_edits_reconstruct_exact_source_and_do_not_modify_interface():
    source='''module m(input clk,rst,active);
reg state_reg,state_next;
always @* begin
state_next=1'b0;
if(active) state_next=state_reg;
end
endmodule
'''
    pool=make_pool(source,{'state_reg':1,'state_next':1,'rst':1,'active':1})
    assert pool
    prefix=source[:source.index(');')+2]
    for item in pool:
        rebuilt=source
        for edit in reversed(item['edits']):
            assert source[edit['start']:edit['end']]==edit['old']
            rebuilt=rebuilt[:edit['start']]+edit['replacement']+rebuilt[edit['end']:]
        assert rebuilt==item['rtl'] and rebuilt.startswith(prefix)


def test_ranking_payload_contains_discovery_only_not_audit_or_labels():
    identity='axis-frame-len-d13_d13';case=load(identity)
    source=(DATA/identity/'input.v').read_text();dependencies=(DATA/identity/'dependencies.v').read_text()
    pool=make_pool(source,{'frame_len_reg':16,'frame_len_next':16,'frame_len_valid_reg':1,'frame_reg':1})
    prompt=messages(case,source,dependencies,pool,{'status':'DISCOVERY_ONLY','traces':[{'cycle':5,'port':'frame_len'}]})
    encoded=json.dumps(prompt)
    assert identity not in encoded and 'control_sources' not in encoded and 'trace_1/' not in encoded and 'trace_2/' not in encoded
    assert '7403' not in encoded and '9601' not in encoded
    assert 'ranked_ids' in encoded and 'DISCOVERY_ONLY' in encoded


def test_empty_ranking_is_declared_static_fallback_order_without_extra_budget():
    identities=[f'candidate_{i:03d}' for i in range(1,15)]
    assert guided_order(identities,[])[:8]==identities[:8]
    reordered=guided_order(identities,[identities[-1],identities[-2]])
    assert reordered[:2]==identities[:2] and len(set(reordered[:8]))==8
