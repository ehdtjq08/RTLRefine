`timescale 1ns/1ps
module tb;
reg input_clk=0, output_clk=0;
always #5 input_clk=~input_clk;
always #7 output_clk=~output_clk;
reg input_rst=1,output_rst=1;
reg [7:0] input_axis_tdata=0;
reg input_axis_tvalid=0,input_axis_tlast=0,input_axis_tuser=0,output_axis_tready=0;
wire input_axis_tready,output_axis_tvalid,output_axis_tlast,output_axis_tuser;
wire [7:0] output_axis_tdata;
axis_async_fifo #(.ADDR_WIDTH(2),.DATA_WIDTH(8)) dut(.*);
integer phase=0, observations, i;
task send;
input [7:0] data;
input last,user;
begin
    @(negedge input_clk);
    input_axis_tdata=data;input_axis_tlast=last;input_axis_tuser=user;input_axis_tvalid=1;
    while(!input_axis_tready) @(negedge input_clk);
    @(posedge input_clk);
    @(negedge input_clk);input_axis_tvalid=0;
end
endtask
always @(posedge output_clk) begin
    $fdisplay(observations,"%0t,%0d,%b,%b,%b,%b,%b,%b,%b",$time,phase,input_rst,output_rst,
        output_axis_tvalid,output_axis_tready,output_axis_tdata,output_axis_tlast,output_axis_tuser);
end
initial begin
    observations=$fopen("observed.csv","w");
    $dumpfile("trace.vcd");$dumpvars(0,tb);
    #60; input_rst=0;output_rst=0;
    repeat(8) @(negedge input_clk);
    phase=1;
    for(i=0;i<1;i=i+1) send(8'ha5+i,1,0);
    repeat(8) @(negedge output_clk);
    phase=2;
    input_rst=1;output_rst=1;
    repeat(6) @(negedge input_clk);
    input_rst=0;output_rst=0;
    repeat(8) @(negedge output_clk);
    phase=3;output_axis_tready=1;
    repeat(10) @(negedge output_clk);
    phase=4;
    send(8'h61,0,1);send(8'h92,1,0);
    repeat(20) @(negedge output_clk);
    $fclose(observations);$finish;
end
initial begin #10000;$fatal(1,"Timed out");end
endmodule
