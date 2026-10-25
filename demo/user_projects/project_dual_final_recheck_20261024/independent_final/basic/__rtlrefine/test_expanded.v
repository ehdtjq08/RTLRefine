// RTLRefine importer example, MIT.
module domain_ticks #(parameter integer WIDTH=80)(
    input wire clk_a, clk_b, reset,
    output reg [WIDTH-1:0] count_a,
    output reg [WIDTH-1:0] count_b
);
always @(posedge clk_a or posedge reset) begin
    if(reset) count_a <= 0;
    else count_a <= count_a + 1;
end
always @(posedge clk_b or posedge reset) begin
    if(reset) count_b <= 0;
    else count_b <= count_b + 1;
end
endmodule
`timescale 1ns/1ps




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
    begin $display("RTLREFINE_PASS nonce=b25255b48e5ba50685dcf739c440f951 checks=%0d", (checks)); $finish; end;
end
endmodule
