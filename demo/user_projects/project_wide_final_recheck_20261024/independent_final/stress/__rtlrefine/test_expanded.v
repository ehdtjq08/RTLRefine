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
    begin $display("RTLREFINE_PASS nonce=26bf4a8d27dabd8aa6decfc39a6f11b5 checks=%0d", (checks)); $finish; end;
end
endmodule
