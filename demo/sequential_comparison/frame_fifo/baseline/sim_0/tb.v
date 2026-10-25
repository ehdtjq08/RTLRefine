`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg rst=1;
reg [7:0] s_axis_tdata=0;
reg s_axis_tkeep=1,s_axis_tvalid=0,s_axis_tlast=0,s_axis_tuser=0,m_axis_tready=0;
reg [1:0] s_axis_tid=0,s_axis_tdest=0;
wire s_axis_tready,m_axis_tvalid,m_axis_tlast,m_axis_tuser,m_axis_tkeep;
wire [7:0] m_axis_tdata;
wire [1:0] m_axis_tid,m_axis_tdest;
wire status_overflow,status_bad_frame,status_good_frame;
axis_fifo #(.ADDR_WIDTH(2),.DATA_WIDTH(8),.KEEP_ENABLE(1),.KEEP_WIDTH(1),
.LAST_ENABLE(1),.ID_ENABLE(1),.ID_WIDTH(2),.DEST_ENABLE(1),.DEST_WIDTH(2),
.USER_ENABLE(1),.USER_WIDTH(1),.FRAME_FIFO(1),.DROP_BAD_FRAME(0),.DROP_WHEN_FULL(0)) dut(.*);
integer cycle=0,observations,statuses,i;
always @(negedge clk) begin
 if(rst) begin cycle=0;m_axis_tready=1;end
 else begin cycle=cycle+1;m_axis_tready=(1'b1);end
end
always @(posedge clk) begin
 $fdisplay(observations,"%0t,%0d,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b",
 $time,cycle,rst,s_axis_tvalid,s_axis_tready,s_axis_tdata,s_axis_tkeep,s_axis_tlast,s_axis_tid,s_axis_tdest,s_axis_tuser,
 m_axis_tvalid,m_axis_tready,m_axis_tdata,m_axis_tkeep,m_axis_tlast,m_axis_tid,m_axis_tdest,m_axis_tuser);
 $fdisplay(statuses,"%0d,%b,%b,%b,%b",cycle,rst,status_overflow,status_bad_frame,status_good_frame);
end
initial begin
 observations=$fopen("observed.csv","w");statuses=$fopen("status.csv","w");$dumpfile("trace.vcd");$dumpvars(0,tb);
 repeat(4) @(negedge clk);rst=0;
 for(i=0;i<24;i=i+1) begin
  s_axis_tdata=(11+9*i)%256;s_axis_tkeep=1;s_axis_tlast=(i%3==2);
  s_axis_tid=(i/3)%4;s_axis_tdest=(i/3+1)%4;s_axis_tuser=(i/3)%2;s_axis_tvalid=1;
  @(posedge clk);while(!s_axis_tready) @(posedge clk);
  @(negedge clk);s_axis_tvalid=0;
 end
 repeat(80) @(negedge clk);$fclose(observations);$fclose(statuses);$finish;
end
initial begin #10000;$fatal(1,"Timed out");end
endmodule
