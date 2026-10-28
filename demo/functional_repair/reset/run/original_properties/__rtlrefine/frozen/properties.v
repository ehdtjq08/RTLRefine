module __rtlrefine_property_top(input clk,rst,s_valid,m_ready,watch_this,
input [WIDTH-1:0] s_data,output s_ready,m_valid,output [WIDTH-1:0] m_data,
output [31:0] expected_count,
output property_valid,property_ready,property_payload,property_stable,property_capacity,cover_progress);
localparam WIDTH=4, DEPTH=4;
packet_queue #(.WIDTH(4),.DEPTH(4)) dut(.clk(clk),.rst(rst),.s_valid(s_valid),.s_ready(s_ready),.s_data(s_data),.m_valid(m_valid),.m_ready(m_ready),.m_data(m_data));
// Universally quantified transaction tracking, independent of circular pointers.
localparam CW=$clog2(DEPTH+2);
reg [CW-1:0] occupancy=0;
wire push=!rst && s_valid && s_ready;
wire pop=!rst && m_valid && m_ready;
always @(posedge clk) begin
    if(rst) occupancy<=0;
    else begin
        case({push,pop})
            2'b10:occupancy<=occupancy+1;
            2'b01:occupancy<=occupancy-1;
            default:occupancy<=occupancy;
        endcase
    end
end
reg tracking=0,seen_watched_pop=0;
reg [CW-1:0] position=0;
reg [WIDTH-1:0] watched_data=0;
always @(posedge clk) begin
    if(rst) begin tracking<=0;position<=0;watched_data<=0;end
    else if(!tracking) begin
        if(push && watch_this) begin
            tracking<=1;position<=occupancy-(pop ? 1 : 0);watched_data<=s_data;
        end
    end else if(pop) begin
        if(position==0) begin tracking<=0;seen_watched_pop<=1;end
        else position<=position-1;
    end
end
reg past_valid=0,was_stalled=0;
reg [WIDTH-1:0] previous_data=0;
always @(posedge clk) begin
    past_valid<=1;
    was_stalled<=!rst && m_valid && !m_ready;
    previous_data<=m_data;
end
always @* if(!past_valid) assume(rst);
assign expected_count=occupancy;
assign property_valid=(m_valid==(!rst && occupancy!=0));
assign property_ready=(s_ready==(!rst && ((occupancy<DEPTH) || (occupancy!=0 && m_ready))));
assign property_payload=rst || !tracking || position!=0 || (m_data==watched_data);
assign property_stable=rst || !was_stalled || (m_valid && m_data==previous_data);
assign property_capacity=(occupancy<=DEPTH);
always @* begin
    assert(property_valid);assert(property_ready);assert(property_payload);
    assert(property_stable);assert(property_capacity);
end
reg seen_push=0,seen_pop=0,seen_full=0,seen_overlap=0,seen_stall=0,seen_reset=0,seen_wrap=0;
reg [CW-1:0] window_pops=0;
always @(posedge clk) begin
    if(push) seen_push<=1;
    if(rst) window_pops<=0;
    else if(pop) begin
        seen_pop<=1;
        if(window_pops<DEPTH) window_pops<=window_pops+1;
        if(window_pops==DEPTH-1) seen_wrap<=1;
    end
    if(!rst && occupancy==DEPTH) seen_full<=1;
    if(push && pop) seen_overlap<=1;
    if(!rst && m_valid && !m_ready) seen_stall<=1;
    if(rst && seen_push) seen_reset<=1;
end
assign cover_progress=seen_push && seen_pop && seen_full && seen_overlap && seen_stall && seen_reset && seen_watched_pop && seen_wrap;
endmodule
