import json
from pathlib import Path

import pytest

from rtl_agent.repair_search.candidates import make_pool
from rtl_agent.repair_search.planner import guided_order,parse,messages
from rtl_agent.repair_search.execution import choose


def test_reset_completion_can_bundle_missing_same_block_state_without_resetting_arrays():
    src='''module m(input clk,rst,write);
reg [3:0] ptr,tail;reg dropping;reg [7:0] mem[0:3];
always @(posedge clk) begin
 if(rst) begin ptr<=0; end
 else if(write) begin tail<=ptr+1;dropping<=1;mem[ptr]<=8'd2;end
end
endmodule
'''
    pool=make_pool(src,{'ptr':4,'tail':4,'dropping':1})
    options=[p for p in pool if p['family']=='reset_completion']
    assert any('tail <= 0;' in p['rtl'] and 'dropping <= 0;' in p['rtl'] for p in options)
    assert not any('mem <= 0' in p['rtl'] for p in options)


def test_condition_grammar_uses_existing_nearby_scalar_and_keeps_original_clocking():
    src='''module m(input clk);
reg zero,reload;reg [7:0] counter;
always @(posedge clk) begin
 if(reload) counter<=3;
 else if(!zero) counter<=counter-1;
end
endmodule
'''
    pool=make_pool(src,{'zero':1,'reload':1,'counter':8})
    assert any(p['family']=='condition_gate' and '(reload) && (zero)' in p['rtl'] for p in pool)
    assert all(p['rtl'].count('posedge clk')==1 for p in pool)


def test_index_and_lane_packing_support_two_site_edits_and_deduplicate():
    src='''module m #(parameter S_COUNT=4,parameter M_COUNT=1)(input clk);
reg [31:0] fifo_a_data,fifo_b_data;wire [31:0] data;
wire x=bits[index*S_COUNT+n];
wire y=other[select*M_COUNT+m];
always @(posedge clk) begin fifo_a_data<=data;fifo_b_data<=data;end
endmodule
'''
    pool=make_pool(src,{'fifo_a_data':32,'fifo_b_data':32,'data':32})
    assert any(p['family']=='index_stride' and p['changed_spans']==2 for p in pool)
    assert any(p['family']=='word_byte_order' and p['changed_spans']==2 for p in pool)
    assert len({p['rtl_sha256'] for p in pool})==len(pool)
    assert len(pool)<=128


def test_ack_pipeline_reuses_clock_and_requires_cycle_signal():
    src='''module m(input clk,i_wb_cyc,stb,output reg o_ack);
wire wb_stb=stb;
always @(posedge clk) o_ack<=wb_stb;
endmodule
'''
    pool=make_pool(src,{'i_wb_cyc':1,'wb_stb':1,'o_ack':1})
    assert any(p['family']=='ack_pipeline' and '__rtlrefine_ack_delay' in p['rtl'] and '!i_wb_cyc' in p['rtl'] for p in pool)
    assert not any(p['family']=='ack_pipeline' for p in make_pool(src,{'wb_stb':1,'o_ack':1}))


def test_reported_accumulator_reset_requires_matching_valid_state():
    src='''module m(input clk);
reg [15:0] count_reg,count_next;reg count_valid_reg;
always @* begin
count_next=count_reg;
if(active) count_next=count_reg+1;
end
endmodule
'''
    pool=make_pool(src,{'count_reg':16,'count_next':16,'count_valid_reg':1})
    assert any(p['family']=='reported_value_reset' and 'if (count_valid_reg) count_next = 0;' in p['rtl'] for p in pool)


def test_guided_order_preserves_common_prefix_and_fills_omitted_ids():
    assert guided_order(['a','b','c','d'],['d','a'])==['a','b','d','c']
    response={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'ranked_ids':['d','d'],'explanation':'bad'})}}]}
    with pytest.raises(ValueError):parse(response,['a','b','c','d'])


def test_selection_stops_on_public_pass_without_access_to_audit():
    calls=[]
    def evaluate(identity):
        calls.append(identity)
        return {'discovery_pass':True,'audit_pass':False,'accepted':False}
    selected,attempted=choose(['a','b','c'],evaluate)
    assert selected=='a' and attempted==['a'] and calls==['a']


def test_staged_admission_matches_frozen_v2_on_the_actual_retention_fix(tmp_path):
    from rtl_agent.known_bugs_v2.cases import DATA
    from rtl_agent.known_bugs_v2.runner import BenchmarkRunner
    from rtl_agent.known_bugs_v2.evaluator import evaluate
    from rtl_agent.repair_search.execution import discover,audit
    from rtl_agent.repair_search.retention import candidates
    r=BenchmarkRunner();ok,why=r.probe(tmp_path/'probe')
    if not ok:pytest.skip(why)
    identity='axis-fifo-d12_d12';source=(DATA/identity/'input.v').read_text();candidate=candidates(source)[0]['rtl']
    staged=discover(identity,candidate,tmp_path/'staged')
    assert staged['discovery_pass'] and not (tmp_path/'staged/evaluation.json').exists()
    final=audit(identity,staged);old=evaluate(identity,candidate,tmp_path/'old')
    assert final['accepted']==old['accepted']==True
    assert [(t['passed'],t['mismatch_count'],t['comparisons']) for t in final['traces']]==[(t['passed'],t['mismatch_count'],t['comparisons']) for t in old['traces']]
