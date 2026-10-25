`timescale 1ns/1ps
`include "rtlrefine_check.vh"
module tb_public;
reg clk_a=0, clk_b=0, reset=0;
wire [79:0] count_a,count_b;
integer checks=0;
domain_ticks #(.WIDTH(80)) dut(.*);
initial begin
    #1;reset=1;#1;reset=0;
    #1;clk_a=1;#1;clk_a=0;
    if(count_a!==80'd1) $fatal(1,"A counter must increment once");
    checks=checks+1;
    #1;clk_b=1;#1;clk_b=0;
    if(count_b!==80'd1) $fatal(1,"B counter increments by the wrong amount actual=%h",count_b);
    checks=checks+1;
    `RTLREFINE_DONE(checks);
end
endmodule
