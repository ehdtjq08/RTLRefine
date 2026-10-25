// RTLRefine importer example, MIT.
module customer_top #(parameter integer WIDTH = 129)(
    input wire [WIDTH-1:0] a, b,
    output wire [WIDTH-1:0] result
);
word_math #(.WIDTH(WIDTH)) math_unit(.a(a), .b(b), .result(result));
endmodule
