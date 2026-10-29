`timescale 1ns/1ps
`include "rtlrefine_check.vh"
module tb_audit;
reg [128:0] a, b;
wire [128:0] result;
integer checks=0;
integer i;
customer_top #(.WIDTH(129)) dut(.a(a),.b(b),.result(result));
initial begin
    for(i=0;i<40;i=i+1) begin
        a={1'b1,$random,$random,$random,$random};
        b={1'b0,$random,$random,$random,$random}; #1;
        if(result !== a+b) $fatal(1,"AUDIT sum mismatch");
        checks=checks+1;
    end
    `RTLREFINE_DONE(checks);
end
endmodule
