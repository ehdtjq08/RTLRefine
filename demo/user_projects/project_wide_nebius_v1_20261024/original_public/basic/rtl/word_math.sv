// RTLRefine importer example, MIT.
module word_math #(parameter integer WIDTH = 129)(
    input wire [WIDTH-1:0] a, b,
    output wire [WIDTH-1:0] result
);
function automatic [WIDTH-1:0] combine(input [WIDTH-1:0] lhs, rhs);
    combine = lhs - rhs;
endfunction
assign result = combine(a, b);
endmodule
