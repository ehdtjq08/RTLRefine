module miter(input clk,rst,input [7:0] s_axis_tdata,input s_axis_tkeep,s_axis_tvalid,s_axis_tlast,
input [1:0] s_axis_tid,s_axis_tdest,input s_axis_tuser,m_axis_tready);
wire c_ready,c_valid,c_last,c_user;
wire [15:0] c_data;wire [1:0] c_keep;wire [1:0] c_id,c_dest;
axis_adapter #(.S_DATA_WIDTH(8),.S_KEEP_ENABLE(0),.S_KEEP_WIDTH(1),
.M_DATA_WIDTH(16),.M_KEEP_ENABLE(1),.M_KEEP_WIDTH(2),.ID_ENABLE(1),.ID_WIDTH(2),
.DEST_ENABLE(1),.DEST_WIDTH(2),.USER_ENABLE(1),.USER_WIDTH(1)) candidate(
.clk(clk),.rst(rst),.s_axis_tdata(s_axis_tdata),.s_axis_tkeep(s_axis_tkeep),.s_axis_tvalid(s_axis_tvalid),
.s_axis_tlast(s_axis_tlast),.s_axis_tid(s_axis_tid),.s_axis_tdest(s_axis_tdest),.s_axis_tuser(s_axis_tuser),
.m_axis_tready(m_axis_tready),.s_axis_tready(c_ready),.m_axis_tvalid(c_valid),.m_axis_tdata(c_data),
.m_axis_tkeep(c_keep),.m_axis_tlast(c_last),.m_axis_tid(c_id),.m_axis_tdest(c_dest),.m_axis_tuser(c_user));
wire g_ready,g_valid,g_last,g_user;
wire [15:0] g_data;wire [1:0] g_keep;wire [1:0] g_id,g_dest;
reference_adapter #(.S_DATA_WIDTH(8),.S_KEEP_ENABLE(0),.S_KEEP_WIDTH(1),
.M_DATA_WIDTH(16),.M_KEEP_ENABLE(1),.M_KEEP_WIDTH(2),.ID_ENABLE(1),.ID_WIDTH(2),
.DEST_ENABLE(1),.DEST_WIDTH(2),.USER_ENABLE(1),.USER_WIDTH(1)) golden(
.clk(clk),.rst(rst),.s_axis_tdata(s_axis_tdata),.s_axis_tkeep(s_axis_tkeep),.s_axis_tvalid(s_axis_tvalid),
.s_axis_tlast(s_axis_tlast),.s_axis_tid(s_axis_tid),.s_axis_tdest(s_axis_tdest),.s_axis_tuser(s_axis_tuser),
.m_axis_tready(m_axis_tready),.s_axis_tready(g_ready),.m_axis_tvalid(g_valid),.m_axis_tdata(g_data),
.m_axis_tkeep(g_keep),.m_axis_tlast(g_last),.m_axis_tid(g_id),.m_axis_tdest(g_dest),.m_axis_tuser(g_user));
always @* begin
assert(c_ready==g_ready);assert(c_valid==g_valid);
if(g_valid) begin
assert(c_keep==g_keep);assert(c_last==g_last);assert(c_id==g_id);assert(c_dest==g_dest);assert(c_user==g_user);
if(g_keep[0]) assert(c_data[0 +: 8]==g_data[0 +: 8]);
if(g_keep[1]) assert(c_data[8 +: 8]==g_data[8 +: 8]);
end
end
endmodule
