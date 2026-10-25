module miter(
input input_clk,output_clk,input_rst,output_rst,
input [7:0] input_axis_tdata,
input input_axis_tvalid,input_axis_tlast,input_axis_tuser,output_axis_tready);
wire c_ready,c_valid,c_last,c_user,g_ready,g_valid,g_last,g_user;
wire [7:0] c_data,g_data;
axis_async_fifo #(.ADDR_WIDTH(2),.DATA_WIDTH(8)) candidate(
.input_clk(input_clk),.output_clk(output_clk),.input_rst(input_rst),.output_rst(output_rst),
.input_axis_tdata(input_axis_tdata),.input_axis_tvalid(input_axis_tvalid),.input_axis_tlast(input_axis_tlast),
.input_axis_tuser(input_axis_tuser),.output_axis_tready(output_axis_tready),
.input_axis_tready(c_ready),.output_axis_tvalid(c_valid),.output_axis_tdata(c_data),.output_axis_tlast(c_last),.output_axis_tuser(c_user));
reference_fifo #(.ADDR_WIDTH(2),.DATA_WIDTH(8)) golden(
.input_clk(input_clk),.output_clk(output_clk),.input_rst(input_rst),.output_rst(output_rst),
.input_axis_tdata(input_axis_tdata),.input_axis_tvalid(input_axis_tvalid),.input_axis_tlast(input_axis_tlast),
.input_axis_tuser(input_axis_tuser),.output_axis_tready(output_axis_tready),
.input_axis_tready(g_ready),.output_axis_tvalid(g_valid),.output_axis_tdata(g_data),.output_axis_tlast(g_last),.output_axis_tuser(g_user));
always @* begin
assert(c_ready==g_ready);
assert(c_valid==g_valid);
if(g_valid) begin assert(c_data==g_data);assert(c_last==g_last);assert(c_user==g_user);end
end
endmodule
