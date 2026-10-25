// RTLRefine importer example, MIT.
module word_math #(parameter integer WIDTH = 129)(
    input wire [WIDTH-1:0] a, b,
    output wire [WIDTH-1:0] result
);
function automatic [WIDTH-1:0] combine(input [WIDTH-1:0] lhs, rhs);
    combine = lhs + rhs;
endfunction
assign result = combine(a, b);
endmodule
// RTLRefine importer example, MIT.
module customer_top #(parameter integer WIDTH = 129)(
    input wire [WIDTH-1:0] a, b,
    output wire [WIDTH-1:0] result
);
word_math #(.WIDTH(WIDTH)) math_unit(.a(a), .b(b), .result(result));
endmodule
`timescale 1ns/1ps




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
    begin $display("RTLREFINE_PASS nonce=003a47c4c17365a841941105ce687565 checks=%0d", (checks)); $finish; end;
end
endmodule
