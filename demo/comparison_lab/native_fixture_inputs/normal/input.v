// RTLRefine integration fixture, MIT, 2026-10-23. Not an AI achievement.
module smoke_counter(input wire clk, input wire rst, input wire en, output wire [7:0] count);
reg [7:0] count_reg=0, count_next;
assign count=count_reg;
always @* begin
    count_next = count_reg;
    if (en) count_next = count_reg + 8'd1;
end
always @(posedge clk) begin
    count_reg <= count_next;
    if (rst) begin
        count_reg <= 0;
    end
end
endmodule
