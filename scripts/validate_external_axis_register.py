"""Validate pinned, unmodified external AXI-stream RTL via the generic importer.

The target is an upstream reverted early-ready throughput regression, not a new
AXI data-corruption discovery. Current source and a test-harness corruption
control qualify the independently authored oracle before inference.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from rtl_agent.common import write_json
from rtl_agent.project_repair.project import load_project,archive_project,read_archive
from rtl_agent.project_repair.workflow import run_project

CASE=ROOT/'external_cases/axis_register_external'

COMMON=r'''`timescale 1ns/1ps
`include "rtlrefine_check.vh"
module TOP;
parameter DATA_WIDTH=8;
parameter REG_TYPE=2;
parameter ALL_ENABLE=1;
parameter SEED=32'h531ea117;
parameter CYCLES=256;
parameter NEGATIVE_DATA_CONTROL=0;
localparam KEEP_WIDTH=DATA_WIDTH/8;
localparam ID_WIDTH=3,DEST_WIDTH=5,USER_WIDTH=2;
localparam WORD_WIDTH=DATA_WIDTH+KEEP_WIDTH+1+ID_WIDTH+DEST_WIDTH+USER_WIDTH;
localparam CAPACITY=(REG_TYPE>1 ? 2 : REG_TYPE==1 ? 1 : 0);
reg clk=0,rst=0,s_axis_tvalid=0,m_axis_tready=0;
reg [DATA_WIDTH-1:0] s_axis_tdata=0;
reg [KEEP_WIDTH-1:0] s_axis_tkeep={KEEP_WIDTH{1'b1}};
reg s_axis_tlast=0;
reg [ID_WIDTH-1:0] s_axis_tid=0;
reg [DEST_WIDTH-1:0] s_axis_tdest=0;
reg [USER_WIDTH-1:0] s_axis_tuser=0;
wire s_axis_tready,m_axis_tvalid,m_axis_tlast;
wire [DATA_WIDTH-1:0] m_axis_tdata;
wire [KEEP_WIDTH-1:0] m_axis_tkeep;
wire [ID_WIDTH-1:0] m_axis_tid;
wire [DEST_WIDTH-1:0] m_axis_tdest;
wire [USER_WIDTH-1:0] m_axis_tuser;
axis_register #(.DATA_WIDTH(DATA_WIDTH),.KEEP_ENABLE(ALL_ENABLE),.KEEP_WIDTH(KEEP_WIDTH),
 .LAST_ENABLE(ALL_ENABLE),.ID_ENABLE(ALL_ENABLE),.ID_WIDTH(ID_WIDTH),
 .DEST_ENABLE(ALL_ENABLE),.DEST_WIDTH(DEST_WIDTH),.USER_ENABLE(ALL_ENABLE),
 .USER_WIDTH(USER_WIDTH),.REG_TYPE(REG_TYPE)) dut(.*);

function [DATA_WIDTH-1:0] qualify_data;
input [DATA_WIDTH-1:0] data;
input [KEEP_WIDTH-1:0] keep;
integer b;
begin
 qualify_data=0;
 for(b=0;b<KEEP_WIDTH;b=b+1)
  if(keep[b]) qualify_data[b*8 +: 8]=data[b*8 +: 8];
end
endfunction

wire [KEEP_WIDTH-1:0] expected_keep=ALL_ENABLE ? s_axis_tkeep : {KEEP_WIDTH{1'b1}};
wire [DATA_WIDTH-1:0] checked_data=m_axis_tdata ^ (NEGATIVE_DATA_CONTROL ? {{(DATA_WIDTH-1){1'b0}},1'b1} : {DATA_WIDTH{1'b0}});
wire [WORD_WIDTH-1:0] input_word={ALL_ENABLE?s_axis_tuser:{USER_WIDTH{1'b0}},
 ALL_ENABLE?s_axis_tdest:{DEST_WIDTH{1'b0}},ALL_ENABLE?s_axis_tid:{ID_WIDTH{1'b0}},
 ALL_ENABLE?s_axis_tlast:1'b1,expected_keep,qualify_data(s_axis_tdata,expected_keep)};
wire [WORD_WIDTH-1:0] output_word={m_axis_tuser,m_axis_tdest,m_axis_tid,m_axis_tlast,m_axis_tkeep,qualify_data(checked_data,m_axis_tkeep)};

reg [WORD_WIDTH-1:0] queue[0:4095];
integer head=0,tail=0,checks=0,total_in=0,total_out=0,discarded=0,serial=0;
integer stalls=0,overlap=0,resets_after_traffic=0,max_pending=0;
reg did_push=0,did_pop=0,previous_stall=0;
reg [WORD_WIDTH-1:0] held_output=0;
reg [31:0] rng=SEED;
integer i,k,before_count,drain_count;

function [31:0] next_rng;
input [31:0] state;
reg [31:0] x;
begin x=state^(state<<13);x=x^(x>>17);next_rng=x^(x<<5);end
endfunction

task word_value;
input integer n;
reg [63:0] mixed;
integer bytes_valid;
begin
 mixed=64'h9e3779b97f4a7c15*n+64'hd1b54a32d192ed03;
 s_axis_tdata=mixed;
 s_axis_tlast=(n%7==6);
 bytes_valid=(n%KEEP_WIDTH)+1;
 s_axis_tkeep=s_axis_tlast ? ((1<<bytes_valid)-1) : {KEEP_WIDTH{1'b1}};
 s_axis_tid=n;s_axis_tdest=(n*3);s_axis_tuser=(n>>1);
end
endtask

task tick;
begin
 #2;
 did_push=0;did_pop=0;
 if(!rst) begin
  if(s_axis_tready!==1'b0 && s_axis_tready!==1'b1) $fatal(1,"UNKNOWN input ready");checks=checks+1;
  if(m_axis_tvalid!==1'b0 && m_axis_tvalid!==1'b1) $fatal(1,"UNKNOWN output valid");checks=checks+1;
  if(previous_stall) begin
   if(!m_axis_tvalid || output_word!==held_output) $fatal(1,"STABILITY output changed while stalled");
   checks=checks+1;
  end
  did_push=s_axis_tvalid && s_axis_tready;
  did_pop=m_axis_tvalid && m_axis_tready;
  // Input first permits legal combinational bypass with zero queue occupancy.
  if(did_push) begin queue[tail]=input_word;tail=tail+1;total_in=total_in+1;end
  if(did_pop) begin
   if(head==tail) $fatal(1,"SPURIOUS output without accepted input");checks=checks+1;
   if(output_word!==queue[head]) $fatal(1,"ORDER_OR_SIDEBAND mismatch received=%h expected=%h",output_word,queue[head]);
   checks=checks+1;head=head+1;total_out=total_out+1;
  end
  if(tail-head>CAPACITY) $fatal(1,"CAPACITY occupancy=%0d capacity=%0d",tail-head,CAPACITY);checks=checks+1;
  if(tail-head>max_pending) max_pending=tail-head;
  if(m_axis_tvalid && !m_axis_tready) stalls=stalls+1;
  if(did_push && did_pop) overlap=overlap+1;
  previous_stall=m_axis_tvalid && !m_axis_tready;held_output=output_word;
 end else begin
  if(total_in>0) resets_after_traffic=resets_after_traffic+1;
  discarded=discarded+(tail-head);head=0;tail=0;previous_stall=0;
 end
 #3;clk=1;#1;clk=0;#4;
end
endtask

task reset_design;
begin rst=1;s_axis_tvalid=0;m_axis_tready=0;tick();tick();rst=0;tick();end
endtask

task drain;
begin
 s_axis_tvalid=0;m_axis_tready=1;
 for(drain_count=0;drain_count<16;drain_count=drain_count+1) tick();
 if(head!=tail || m_axis_tvalid) $fatal(1,"DRAIN did not deliver every accepted transfer");
 checks=checks+1;
end
endtask

task capacity_after_idle_gap;
begin
 reset_design();m_axis_tready=0;s_axis_tvalid=1;word_value(serial);serial=serial+1;
 before_count=total_in;
 for(k=0;k<4;k=k+1) begin tick();if(did_push) k=4;end
 if(total_in!=before_count+1) $fatal(1,"FIRST_SLOT no input accepted");checks=checks+1;
 s_axis_tvalid=0;
 tick();tick();tick();
 if(tail-head!=1) $fatal(1,"SETUP expected one queued transfer");checks=checks+1;
 s_axis_tvalid=1;word_value(serial);serial=serial+1;before_count=total_in;
 for(k=0;k<4;k=k+1) begin tick();if(did_push) k=4;end
 if(total_in!=before_count+1) $fatal(1,"CAPACITY_READY_REGRESSION second skid slot unavailable after input idle gap while output stalled");
 checks=checks+1;
 s_axis_tvalid=0;drain();
end
endtask
'''

PUBLIC=r'''
initial begin
 capacity_after_idle_gap();
 if(total_in!=2 || total_out!=2 || max_pending!=2) $fatal(1,"PUBLIC coverage incomplete");checks=checks+1;
 `RTLREFINE_DONE(checks);
end
endmodule
'''

AUDIT=r'''
initial begin
 if(REG_TYPE>1) capacity_after_idle_gap();else reset_design();
 // Continuous traffic validates the documented no-bubble skid/bypass path.
 before_count=total_out;
 for(i=0;i<40;i=i+1) begin
  if(!s_axis_tvalid || did_push) begin word_value(serial);serial=serial+1;end
  s_axis_tvalid=1;m_axis_tready=1;tick();
 end
 if(REG_TYPE!=1 && total_out-before_count<38) $fatal(1,"THROUGHPUT missing steady-state transfers");checks=checks+1;
 drain();reset_design();
 for(i=0;i<CYCLES;i=i+1) begin
  rng=next_rng(rng);
  if(i==73 || i==371) begin rst=1;s_axis_tvalid=0;m_axis_tready=0;end
  else begin
   rst=0;
   if(!s_axis_tvalid || did_push) begin
    s_axis_tvalid=(rng[1:0]!=0);
    if(s_axis_tvalid) begin word_value(serial);serial=serial+1;end
   end
   m_axis_tready=(i%113>=19) && (rng[3:2]!=0);
  end
  tick();
 end
 rst=0;
 // Complete any source transfer held over the final stall before draining.
 for(i=0;i<8;i=i+1) begin
  m_axis_tready=1;tick();if(did_push) s_axis_tvalid=0;
 end
 drain();
 if(total_in<40 || total_out<20 || stalls<10) $fatal(1,"AUDIT traffic coverage incomplete");checks=checks+1;
 if(REG_TYPE>1 && (overlap<10 || max_pending!=2)) $fatal(1,"AUDIT skid traffic incomplete");checks=checks+1;
 if(total_in!=total_out+discarded) $fatal(1,"CONSERVATION accepted != delivered + reset discarded");checks=checks+1;
 $display("EXTERNAL_COVERAGE in=%0d out=%0d reset_discarded=%0d stalls=%0d overlap=%0d max_pending=%0d",total_in,total_out,discarded,stalls,overlap,max_pending);
 `RTLREFINE_DONE(checks);
end
endmodule
'''

PROFILES=[
 ('skid8',8,2,1,0x13579bdf,1024),('skid32',32,2,1,0x9ace0123,1024),
 ('skid64',64,2,1,0x31415927,1536),('simple16',16,1,1,0x2468ace1,768),
 ('bypass8',8,0,1,0x10293847,512),('disabled32',32,2,0,0x19283746,1024),
 ('reset_stall8',8,2,1,0x27182819,512)]


def files_for(revision,*,negative=False):
    provenance=json.loads((CASE/'provenance.json').read_text());raw=(CASE/revision/'rtl/axis_register.v').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==provenance['revisions'][revision]['sha256']
    files={'rtl/axis_register.v':raw,'UPSTREAM_LICENSE':(CASE/'UPSTREAM_LICENSE').read_bytes(),
           'tests/public.sv':(COMMON.replace('module TOP;','module tb_public;')+PUBLIC).encode(),
           'tests/audit.sv':(COMMON.replace('module TOP;','module tb_audit;')+AUDIT).encode()}
    tests=[{'id':'capacity_public','phase':'public','top':'tb_public','files':['tests/public.sv'],
            'parameters':{'NEGATIVE_DATA_CONTROL':1 if negative else 0}}]
    for name,width,mode,enabled,seed,cycles in PROFILES:
        tests.append({'id':name,'phase':'audit','top':'tb_audit','files':['tests/audit.sv'],
            'parameters':{'DATA_WIDTH':width,'REG_TYPE':mode,'ALL_ENABLE':enabled,'SEED':seed,'CYCLES':cycles}})
    config={'schema_version':1,'name':'External verilog-axis AXI register '+revision+(' · negative harness control' if negative else ''),
            'dut_top':'axis_register','rtl_files':['rtl/axis_register.v'],'editable_files':['rtl/axis_register.v'],
            'dut_parameters':{'DATA_WIDTH':8,'KEEP_WIDTH':1,'KEEP_ENABLE':1,'LAST_ENABLE':1,'ID_ENABLE':1,'ID_WIDTH':3,
                              'DEST_ENABLE':1,'DEST_WIDTH':5,'USER_ENABLE':1,'USER_WIDTH':2,'REG_TYPE':2},
            'contract':'REG_TYPE=2 is a two-entry skid buffer: after one accepted word, an input idle gap while output is stalled must not make the second slot unavailable. Preserve accepted AXI4-Stream payload order and enabled sidebands, stability during output stalls, reset flushing and documented register modes. No corrected RTL reference is supplied.',
            'tests':tests}
    files['rtlrefine.json']=json.dumps(config,indent=2).encode()
    files['PROVENANCE.json']=json.dumps({'revision':revision,**provenance['revisions'][revision],
                                      'source_modified':False,'oracle':'Independent transaction scoreboard and documented skid capacity; no golden RTL'},indent=2).encode()
    return files


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['qualify','repair']);p.add_argument('--output',required=True);args=p.parse_args()
    out=Path(args.output).resolve();out.mkdir(exist_ok=False)
    if args.action=='qualify':
        rows=[]
        for name,rev,negative in [('current','current',False),('regressed','regressed',False),('negative_harness_control','current',True)]:
            project=load_project(files_for(rev,negative=negative));(out/(name+'.zip')).write_bytes(archive_project(project))
            result=run_project(project,output=out/name,on_event=lambda e:print(name+': '+e['message'],flush=True))
            row={'name':name,'accepted':result['accepted'],'status':result['status'],'api_requests':result['api_requests'],
                 'tests':[{k:t.get(k) for k in ['id','phase','status','checks','log_tail']} for t in result.get('final_check',result['baseline'])['tests']]}
            rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='tests'}),flush=True)
        write_json(out/'qualification.json',{'cohort':'pinned external RTL and explicit harness control','results':rows,'new_model_calls':0})
    else:
        qualified=ROOT/'results/external_axis_register_qualification_v1/qualification.json'
        q=json.loads(qualified.read_text());assert q['results'][0]['accepted'] and not q['results'][1]['accepted'] and not q['results'][2]['accepted']
        result=run_project(load_project(files_for('regressed')),repair=True,output=out/'run',on_event=lambda e:print(e['message'],flush=True))
        write_json(out/'summary.json',{k:result.get(k) for k in ['status','accepted','api_requests','wall_seconds']})
        print(json.dumps({k:result.get(k) for k in ['status','accepted','api_requests','wall_seconds']},indent=2))


if __name__=='__main__':main()
