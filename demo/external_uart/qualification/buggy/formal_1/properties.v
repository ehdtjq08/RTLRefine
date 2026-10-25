module property_top(input i_clk,i_reset,i_break,
output o_busy,o_uart_tx,property_blocked,output [3:0] age);
txuart #(.INITIAL_SETUP(31'd5)) dut(
.i_clk(i_clk),.i_reset(i_reset),.i_setup(31'd5),
.i_break(i_break),.i_wr(1'b0),.i_data(8'd0),.i_cts_n(1'b1),
.o_busy(o_busy),.o_uart_tx(o_uart_tx));
reg [3:0] stable_age=0;
reg past_valid=0;
always @(posedge i_clk) begin
 past_valid<=1;
 if(stable_age<15) stable_age<=stable_age+1'b1;
end
always @* if(!past_valid) assume(i_reset);
assign age=stable_age;
assign property_blocked=(stable_age<8) || o_busy;
always @* assert(property_blocked);
endmodule
