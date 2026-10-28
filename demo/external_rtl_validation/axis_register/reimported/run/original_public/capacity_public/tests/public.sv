`timescale 1ns/1ps
`include "rtlrefine_check.vh"
module tb_public;
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

initial begin
 capacity_after_idle_gap();
 if(total_in!=2 || total_out!=2 || max_pending!=2) $fatal(1,"PUBLIC coverage incomplete");checks=checks+1;
 `RTLREFINE_DONE(checks);
end
endmodule
