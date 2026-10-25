`timescale 1ns/1ps
`include "rtlrefine_check.vh"
module tb_public;
reg [128:0] a, b;
wire [128:0] result;
integer checks=0;
customer_top #(.WIDTH(129)) dut(.a(a),.b(b),.result(result));
initial begin
    a=129'd5; b=129'd2; #1;
    if (result !== a+b) $fatal(1,"SUM mismatch actual=%h expected=%h",result,a+b);
    checks=checks+1;
    a=(129'd1 << 128); b=129'd3; #1;
    if (result !== a+b) $fatal(1,"WIDE mismatch actual=%h expected=%h",result,a+b);
    checks=checks+1;
    `RTLREFINE_DONE(checks);
end
endmodule
