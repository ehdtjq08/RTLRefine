import copy
import json
from pathlib import Path

import pytest

from rtl_agent.common import ROOT
from rtl_agent.known_bugs_v2.agent import apply_proposal, messages
from rtl_agent.known_bugs_v2.cases import DATA, load, source_policy, canonical
from rtl_agent.known_bugs_v2.evaluator import evaluate, feedback, _editable_ports
from rtl_agent.known_bugs_v2.runner import BenchmarkRunner

FRAME = "axis-frame-len-d13_d13"


@pytest.fixture
def runner(tmp_path):
    r = BenchmarkRunner()
    ok, detail = r.probe(tmp_path / "isolation")
    if not ok:
        pytest.skip(detail)
    return r


def test_known_maintainer_fixes_are_representable_and_allowed():
    for path in sorted(DATA.glob('*/case.json')):
        case = json.loads(path.read_text())
        if case["kind"] != "historical_defect":
            continue
        original = (path.parent / "input.v").read_text()
        fixed = (ROOT / "research/known_bug_benchmark/control_sources_v2" / (case["id"] + ".v")).read_text()
        ports = case["ports"] if case["top"] == case["edited_module"] else _editable_ports(original)
        source_policy(original, original, ports)
        source_policy(fixed, original, ports)
    case = load("zipcpu-spi-c1-c3-d9_c1")
    original = (DATA / case["id"] / "input.v").read_text()
    fixed = (ROOT / "research/known_bug_benchmark/control_sources_v2" / (case["id"] + ".v")).read_text()
    old, new = original.splitlines(), fixed.splitlines()
    changed = [i for i,(a,b) in enumerate(zip(old,new),1) if a!=b]
    assert len(changed)==1
    i=changed[0]
    repaired=apply_proposal({"decision":"repair","edits":[{"start_line":i,"end_line":i,"replacement":new[i-1]}],"explanation":"test-only real maintainer line edit"},original)
    assert canonical(repaired)==canonical(fixed)
    names=_editable_ports(original)
    assert {"i_clk","i_speed","i_cs","i_stb","i_byte","i_bus_grant","i_miso"} <= set(names)


def test_line_edits_reject_overlap_bad_bounds_and_hidden_keep_changes():
    original=(DATA/FRAME/"input.v").read_text()
    for edits in ([{"start_line":1,"end_line":1,"replacement":"x"}],
                  [{"start_line":80,"end_line":83,"replacement":"x"},{"start_line":82,"end_line":84,"replacement":"y"}]):
        with pytest.raises(ValueError):
            apply_proposal({"decision":"repair","edits":edits,"explanation":"invalid"},original)
    with pytest.raises(ValueError):
        apply_proposal({"decision":"keep","edits":[{"start_line":80,"end_line":80,"replacement":"x"}],"explanation":"invalid"},original)


def test_source_policy_rejects_file_tasks_input_drivers_and_checker_access():
    case=load(FRAME);source=(DATA/FRAME/"input.v").read_text()
    for added in ('initial $readmemh("expected.hex", memory);','assign monitor_axis_tvalid=0;',
                  'wire bad=harness.secret;','always @* assume(1);','// verilator public\nwire exposed;'):
        with pytest.raises(ValueError):
            source_policy(source.replace("endmodule",added+'\nendmodule'),source,case['ports'])


def test_prompt_hides_case_labels_fix_and_audit_values():
    case=load(FRAME);source=(DATA/FRAME/"input.v").read_text();deps=(DATA/FRAME/"dependencies.v").read_text()
    text=json.dumps(messages(case,source,deps))
    assert FRAME not in text and "control_sources_v2" not in text and "trace_1/" not in text
    assert "9601" not in text and "7403" not in text
    assert "First editable line" in text


def test_scoring_never_reads_corrected_rtl_and_audit_never_enters_feedback(tmp_path,runner,monkeypatch):
    source=(ROOT/'research/known_bug_benchmark/control_sources_v2'/f'{FRAME}.v').read_text()
    read_text,read_bytes=Path.read_text,Path.read_bytes
    def deny(path):
        if path.resolve().is_relative_to((ROOT/'research').resolve()) or path.resolve().is_relative_to((ROOT/'third_party').resolve()):
            pytest.fail('Admission read a corrected RTL source or upstream research code')
    def text(path,*a,**k):
        deny(path);return read_text(path,*a,**k)
    def data(path,*a,**k):
        deny(path);return read_bytes(path,*a,**k)
    monkeypatch.setattr(Path,'read_text',text);monkeypatch.setattr(Path,'read_bytes',data)
    r=evaluate(FRAME,source,tmp_path/'control',runner=runner)
    assert r['accepted'] and r['corrected_RTL_loaded_for_scoring'] is False
    altered=copy.deepcopy(r)
    for trace in altered['traces'][1:]:
        trace['passed']=False;trace['first_mismatches']=[{'audit':'private'}]
    altered['audit_pass']=False;altered['accepted']=False
    assert feedback(r)==feedback(altered)


def test_memorizing_published_trace_is_rejected_by_extra_audit(tmp_path,runner):
    original=(DATA/FRAME/'input.v').read_text()
    prefix=original[:original.index(');')+2]
    source=prefix+'''
reg [2:0] replay_counter=0;
always @(posedge clk) replay_counter<=replay_counter+1'b1;
assign frame_len=(replay_counter==3)?1:((replay_counter==4)?2:((replay_counter==5)?1:0));
assign frame_len_valid=(replay_counter==4 || replay_counter==5);
endmodule
'''
    r=evaluate(FRAME,source,tmp_path/'overfit',runner=runner)
    assert r['discovery_pass'] and not r['audit_pass'] and not r['accepted']
    assert r['status']=='AUDIT_FAILED'


def test_extra_audit_failure_never_triggers_a_second_model_request(tmp_path):
    from scripts.run_known_bug_comparison_v2 import run_pair
    requests=[]
    def request(*a,**k):
        requests.append((a,k))
        return {'status':'AUDIT_FAILED','accepted':False,'discovery_pass':True,'audit_pass':False,
                'proposal':{'decision':'repair'},'functional_source_changed':True}
    p=run_pair({'opaque_id':'case_01','case_id':FRAME},tmp_path/'pair',request)
    assert len(requests)==1
    assert all(a['logical_calls']==1 and a['would_accept_on_discovery_but_audit_fails'] for a in p['arms'].values())


def test_self_review_receives_no_execution_observation(tmp_path):
    from scripts.run_known_bug_comparison_v2 import run_pair
    calls=[]
    def request(*a,**k):
        calls.append((a[3].name,k))
        return {'status':'DISCOVERY_TRACE_FAILED','accepted':False,'discovery_pass':False,'audit_pass':False,
                'proposal':{'decision':'keep','edits':[],'explanation':'test'},'functional_source_changed':False,
                'evaluation':{'traces':[{'phase':'discovery','first_mismatches':[{'signal':'public'}]}]}}
    run_pair({'opaque_id':'case_02','case_id':FRAME},tmp_path/'pair',request)
    by_name=dict(calls)
    assert by_name['self_review']['observations'] is None
    assert by_name['checker_feedback']['observations']['traces'][0]['first_mismatches']==[{'signal':'public'}]


def test_oracle_masks_invalid_payload_and_debug_outputs(tmp_path):
    from rtl_agent.known_bugs_v2.engine import qualify_expected_file
    p=tmp_path/'expected.hex'
    names=['frame_len','frame_len_valid','m_axis_tdata','m_axis_tvalid','o_wb_data','o_wb_ack','o_debug']
    p.write_text('a 0 ab 0 cc 0 ff\na 1 ab 1 cc 1 ff\n')
    qualify_expected_file(p,names)
    assert p.read_text().splitlines()==['? 0 ? 0 ? 0 ?', 'a 1 ab 1 cc 1 ?']


def test_independent_length_guard_rejects_wrong_or_out_of_domain_oracle(tmp_path):
    from rtl_agent.known_bugs_v2.engine import verify_frame_length_oracle
    stim=tmp_path/'input.hex';expected=tmp_path/'expected.hex'
    stim.write_text('1 0 0 0 0\n0 3 1 1 1\n0 0 0 1 0\n')
    expected.write_text('? 0\n? 0\n2 1\n')
    trace={'inputs':['rst','monitor_axis_tkeep','monitor_axis_tvalid','monitor_axis_tready','monitor_axis_tlast'],
           'outputs':['frame_len','frame_len_valid'],'stimulus':str(stim),'expected':str(expected)}
    ports={'frame_len':{'width':16}}
    assert verify_frame_length_oracle(trace,ports)['applicable']
    expected.write_text('? 0\n? 0\n3 1\n')
    with pytest.raises(ValueError,match='independent byte count'):
        verify_frame_length_oracle(trace,ports)
    stim.write_text('1 0 0 0 0\n0 5 1 1 1\n0 0 0 1 0\n')
    with pytest.raises(ValueError,match='Noncontiguous'):
        verify_frame_length_oracle(trace,ports)


def test_v1_popcount_improvement_is_not_falsely_rejected(tmp_path,runner):
    source=(ROOT/'research/known_bug_benchmark/v1_oracle_discrepancy/candidate.v').read_text()
    r=evaluate(FRAME,source,tmp_path/'legitimate_improvement',runner=runner)
    assert r['accepted'],r
