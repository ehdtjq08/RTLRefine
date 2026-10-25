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




module tb_audit;
reg clk_a=0,clk_b=0,reset=0;
wire [79:0] count_a,count_b;
reg [79:0] want_a=0,want_b=0;
integer checks=0,i;
domain_ticks #(.WIDTH(80)) dut(.*);
initial begin
    #1;reset=1;#1;reset=0;
    for(i=0;i<25;i=i+1) begin
        #2;clk_b=1;want_b=want_b+1;#1;clk_b=0;
        if(i%3==0) begin #2;clk_a=1;want_a=want_a+1;#1;clk_a=0; end
        if(count_a!==want_a || count_b!==want_b) $fatal(1,"Clock-domain counter mismatch");
        checks=checks+1;
    end
    begin $display("RTLREFINE_PASS nonce=771ac15b832b6ae118ac8aa8f945f6c2 checks=%0d", (checks)); $finish; end;
end
endmodule
