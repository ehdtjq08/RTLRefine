"""Healthy compatibility control from a second independent RTL author."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.validate_external_axis_register import COMMON,PUBLIC,AUDIT,PROFILES
from rtl_agent.project_repair.project import load_project,archive_project
from rtl_agent.project_repair.workflow import run_project

CASE=ROOT/'external_cases/zipcpu_skid_external'


def files_for(negative=False):
    meta=json.loads((CASE/'provenance.json').read_text());source=(CASE/'rtl/skidbuffer.v').read_bytes()
    assert hashlib.sha256(source).hexdigest()==meta['source_sha256']
    # Reuse an attributed MIT interface declaration; the leaf itself is unmodified.
    axis=(ROOT/'external_cases/axis_register_external/current/rtl/axis_register.v').read_text()
    header=axis.split('\ngenerate\n',1)[0].replace('module axis_register','module skid_axis_adapter')
    header=re.sub(r'parameter REG_TYPE\s*=\s*2',r'parameter LOWPOWER = 1,\n    parameter REG_TYPE = 2',header)
    adapter=header+'''
// RTLRefine-owned stateless adapter: pack metadata into the leaf's data bus.
localparam WORD_WIDTH=DATA_WIDTH+KEEP_WIDTH+1+ID_WIDTH+DEST_WIDTH+USER_WIDTH;
wire [WORD_WIDTH-1:0] packed_in={USER_ENABLE?s_axis_tuser:{USER_WIDTH{1'b0}},
 DEST_ENABLE?s_axis_tdest:{DEST_WIDTH{1'b0}},ID_ENABLE?s_axis_tid:{ID_WIDTH{1'b0}},
 LAST_ENABLE?s_axis_tlast:1'b1,KEEP_ENABLE?s_axis_tkeep:{KEEP_WIDTH{1'b1}},s_axis_tdata};
wire [WORD_WIDTH-1:0] packed_out;
skidbuffer #(.DW(WORD_WIDTH),.OPT_LOWPOWER(LOWPOWER),.OPT_OUTREG(REG_TYPE>1),
 .OPT_PASSTHROUGH(REG_TYPE==0),.OPT_INITIAL(1)) leaf(
 .i_clk(clk),.i_reset(rst),.i_valid(s_axis_tvalid),.o_ready(s_axis_tready),
 .i_data(packed_in),.o_valid(m_axis_tvalid),.i_ready(m_axis_tready),.o_data(packed_out));
assign {m_axis_tuser,m_axis_tdest,m_axis_tid,m_axis_tlast,m_axis_tkeep,m_axis_tdata}=packed_out;
endmodule
`resetall
'''
    common=COMMON.replace('axis_register #(','skid_axis_adapter #(')
    common=common.replace('parameter NEGATIVE_DATA_CONTROL=0;','parameter NEGATIVE_DATA_CONTROL=0;\nparameter LOWPOWER=1;')
    common=common.replace('.USER_WIDTH(USER_WIDTH),.REG_TYPE(REG_TYPE)) dut', '.USER_WIDTH(USER_WIDTH),.REG_TYPE(REG_TYPE),.LOWPOWER(LOWPOWER)) dut')
    tests=[{'id':'capacity_public','phase':'public','top':'tb_public','files':['tests/public.sv'],
            'parameters':{'NEGATIVE_DATA_CONTROL':int(negative)}}]
    for i,(name,width,mode,enabled,seed,cycles) in enumerate(PROFILES):
        tests.append({'id':name,'phase':'audit','top':'tb_audit','files':['tests/audit.sv'],
                      'parameters':{'DATA_WIDTH':width,'REG_TYPE':mode,'ALL_ENABLE':enabled,'SEED':seed,'CYCLES':cycles,'LOWPOWER':i%2}})
    cfg={'schema_version':1,'name':'External ZipCPU skid buffer · unmodified healthy control'+(' · negative harness control' if negative else ''),
         'dut_top':'skid_axis_adapter','rtl_files':['rtl/skidbuffer.v','rtl/skid_axis_adapter.v'],'editable_files':['rtl/skidbuffer.v'],
         'dut_parameters':{'DATA_WIDTH':8,'KEEP_WIDTH':1,'KEEP_ENABLE':1,'LAST_ENABLE':1,'ID_ENABLE':1,'ID_WIDTH':3,'DEST_ENABLE':1,'DEST_WIDTH':5,'USER_ENABLE':1,'USER_WIDTH':2,'REG_TYPE':2,'LOWPOWER':1},
         'contract':'Preserve accepted transaction order and sidebands, stalled output stability and reset flushing through the unmodified skid buffer. The stateless wrapper packs sidebands into data. This is a healthy compatibility control, not a requested bug repair.',
         'tests':tests}
    return {'rtl/skidbuffer.v':source,'rtl/skid_axis_adapter.v':adapter.encode(),
            'UPSTREAM_APACHE_LICENSE':(CASE/'UPSTREAM_LICENSE').read_bytes(),
            'PROVENANCE.json':json.dumps(meta,indent=2).encode(),
            'rtlrefine.json':json.dumps(cfg,indent=2).encode(),
            'tests/public.sv':(common.replace('module TOP;','module tb_public;')+PUBLIC).encode(),
            'tests/audit.sv':(common.replace('module TOP;','module tb_audit;')+AUDIT).encode()}


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output);out.mkdir(exist_ok=False);rows=[]
    for name,negative in [('healthy',False),('negative_harness_control',True)]:
        project=load_project(files_for(negative));(out/(name+'.zip')).write_bytes(archive_project(project))
        r=run_project(project,output=out/name,on_event=lambda e:print(name+': '+e['message'],flush=True))
        row={'name':name,'accepted':r['accepted'],'status':r['status'],'api_requests':r['api_requests'],
             'tests':[{k:t.get(k) for k in ['id','status','checks','log_tail']} for t in r.get('final_check',r['baseline'])['tests']]}
        rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='tests'}),flush=True)
    (out/'qualification.json').write_text(json.dumps({'cohort':'Second independent author, healthy source + explicit observed-bus corruption control','results':rows,'new_model_calls':0},indent=2)+'\n')


if __name__=='__main__':main()
