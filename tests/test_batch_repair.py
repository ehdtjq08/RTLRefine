import pytest

from rtl_agent.common import sha256
from rtl_agent.batch_repair.schema import add_selector,instrument,partition,SELECTOR


def candidate(source,identity,edits,family='condition_gate'):
    result=source
    for a,b,replacement in sorted(edits,reverse=True):result=result[:a]+replacement+result[b:]
    return {'id':identity,'family':family,'edits':[{'start':a,'end':b,'old':source[a:b],'replacement':r} for a,b,r in edits],
            'rtl':result,'rtl_sha256':sha256(result.encode())}


def test_selector_keeps_ansi_and_classic_module_headers_well_formed():
    assert ', input wire [7:0] '+SELECTOR in add_selector('module m(input wire clk); endmodule','m')
    text=add_selector('module m(clk); input wire clk; endmodule','m')
    assert 'module m(clk, '+SELECTOR+');' in text and 'input wire [7:0] '+SELECTOR+';' in text


def test_multisite_patch_uses_one_selector_and_preserves_exact_original_edits():
    source='module m(input wire clk); reg a,b; always @(posedge clk) begin a<=0; b<=0; end endmodule'
    x=source.index('0');y=source.index('0',x+1)
    pool=[candidate(source,'one',[(x,x+1,'1')]),candidate(source,'two',[(x,x+1,'1'),(y,y+1,'1')])]
    text,deps,selectors=instrument(source,'',{'top':'m','edited_module':'m'},pool)
    assert selectors=={'one':1,'two':2} and 'rtlrefine_patch_select == 1 || rtlrefine_patch_select == 2' in text
    assert text.count('rtlrefine_patch_select == 2')==2


def test_child_instrumentation_adds_top_port_without_changing_child_interface():
    source='module child(input wire clk); reg a; always @(posedge clk) begin a<=0; end endmodule'
    a=source.index('0');p=candidate(source,'one',[(a,a+1,'1')])
    text,deps,_=instrument(source,'module top(input wire clk); child u(clk); endmodule',{'top':'top','edited_module':'child'},[p])
    assert 'top.'+SELECTOR in text and 'input wire [7:0] '+SELECTOR not in text
    assert 'input wire [7:0] '+SELECTOR in deps


def test_elaboration_only_edits_take_the_standalone_path():
    source='module m(input wire clk); generate if (1) begin end endgenerate endmodule'
    a=source.index('1');p=candidate(source,'one',[(a,a+1,'0')])
    supported,fallback=partition(source,[p]);assert not supported and len(fallback)==1


def test_candidate_hash_tampering_cannot_enter_the_batch():
    source='module m(input wire clk); reg a; always @(posedge clk) begin a<=0; end endmodule'
    a=source.index('0');p=candidate(source,'one',[(a,a+1,'1')]);p['rtl_sha256']='0'*64
    with pytest.raises(ValueError,match='hash'):instrument(source,'',{'top':'m','edited_module':'m'},[p])


def test_original_public_pass_still_requires_independent_admission(tmp_path,monkeypatch):
    from rtl_agent.batch_repair.workflow import original,repair
    source=original('reset');calls=[]
    monkeypatch.setattr('rtl_agent.batch_repair.workflow.discover',lambda *a,**k:{'discovery_pass':True,'traces':[{'passed':True}]})
    def final(*a,**k):
        calls.append(1);return {'status':'AUDIT_FAILED','accepted':False,'traces':[{'passed':True},{'passed':False},{'passed':False}]}
    monkeypatch.setattr('rtl_agent.batch_repair.workflow.evaluate',final)
    monkeypatch.setattr('rtl_agent.batch_repair.workflow.diagnose',lambda *a,**k:pytest.fail('No inference on public-pass path'))
    result=repair('reset',source,live=True,output=str(tmp_path/'repair'))
    assert len(calls)==1 and not result['accepted'] and result['api_requests']==0


def test_native_execution_failure_never_triggers_paid_diagnosis(tmp_path,monkeypatch):
    from rtl_agent.batch_repair.workflow import original,repair
    monkeypatch.setattr('rtl_agent.batch_repair.workflow.discover',lambda *a,**k:{'discovery_pass':False,
        'traces':[{'passed':False,'cycles':0,'first_mismatches':[],'command':{'status':'FAIL'}}]})
    monkeypatch.setattr('rtl_agent.batch_repair.workflow.diagnose',lambda *a,**k:pytest.fail('Cannot bill for an unavailable native witness'))
    result=repair('reset',original('reset'),live=True,output=str(tmp_path/'repair'))
    assert result['status']=='ORIGINAL_CHECK_UNAVAILABLE' and result['api_requests']==0
