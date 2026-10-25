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
    else count_b <= count_b + 2;
end
endmodule
