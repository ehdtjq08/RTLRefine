from rtl_agent.repair_search.retention import candidates


def test_only_straight_line_defaults_are_candidates_not_reset_or_branch_assignments():
    source = '''module demo(input clk,rst);
reg state_reg, state_next, pulse_reg, pulse_next;
always @* begin
 state_next = 1'b0;
 pulse_next = 1'b0;
 if(rst) state_next=1'b0;
 else state_next=1'b1;
end
always @(posedge clk) if(rst) state_reg<=0;
endmodule
'''
    options = candidates(source)
    assert [o['state'] for o in options] == ['state', 'pulse']
    assert all(o['changed_source_spans'] == 1 for o in options)
    assert options[0]['rtl'].count("if(rst) state_next=1'b0;") == 1


def test_comments_and_missing_state_register_cannot_create_false_sites():
    source = '''module demo;
reg data_reg, data_next;
// always @* begin fake_next=0;
always @(*) begin
 /* dummy_next=0; if(cheat) */
 missing_next=0;
 data_next=1'b0;
 if(active) data_next=data_reg;
end
endmodule
'''
    options = candidates(source)
    assert len(options) == 1 and options[0]['state'] == 'data'
    assert 'data_next=data_reg' in options[0]['rtl']
