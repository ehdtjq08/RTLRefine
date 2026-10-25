module property_top(
input clk,rst,input [7:0] s_data,input s_valid,s_last,s_user,m_ready,
input [3:0] watched_bit,
output s_ready,m_valid,m_last,m_user,output [7:0] m_data,
output property_valid,property_ready,property_payload,property_stable,property_capacity,
output [2:0] expected_count);
localparam ADDR_WIDTH=2;
localparam DEPTH=1<<ADDR_WIDTH;
stream_buffer #(.ADDR_WIDTH(ADDR_WIDTH),.DATA_WIDTH(8)) dut(
.clk(clk),.rst(rst),.s_data(s_data),.s_valid(s_valid),.s_ready(s_ready),.s_last(s_last),.s_user(s_user),
.m_data(m_data),.m_valid(m_valid),.m_ready(m_ready),.m_last(m_last),.m_user(m_user));

// A transaction-level shift queue, independent of the DUT's circular pointers.
reg spec_queue[0:DEPTH-1];
reg [ADDR_WIDTH:0] spec_count=0;
wire push=!rst && s_valid && s_ready;
wire pop=!rst && m_valid && m_ready;
wire [9:0] input_word={s_last,s_user,s_data};
wire [9:0] output_word={m_last,m_user,m_data};
wire selected_input=input_word[watched_bit];
integer i;
always @(posedge clk) begin
 if(rst) spec_count<=0;
 else begin
  if(pop) begin
   for(i=0;i<DEPTH-1;i=i+1) spec_queue[i]<=spec_queue[i+1];
  end
  if(push) spec_queue[spec_count-(pop ? 1'b1 : 1'b0)]<=selected_input;
  case({push,pop})
   2'b10:spec_count<=spec_count+1'b1;
   2'b01:spec_count<=spec_count-1'b1;
   default:spec_count<=spec_count;
  endcase
 end
end
reg past_valid=0,past_source_held=0,past_output_held=0;
reg [9:0] past_input=0,past_output=0;
reg [3:0] past_bit=0;
always @(posedge clk) begin
 past_valid<=1;
 past_source_held<=!rst && s_valid && !s_ready;
 past_output_held<=!rst && m_valid && !m_ready;
 past_input<=input_word;past_output<=output_word;past_bit<=watched_bit;
end
always @* begin
 if(!past_valid) assume(rst);
 assume(watched_bit<10);
 if(past_valid) assume(watched_bit==past_bit);
 if(past_source_held && !rst) begin assume(s_valid);assume(input_word==past_input);end
end
assign expected_count=spec_count;
assign property_valid=(m_valid==(!rst && spec_count!=0));
assign property_ready=(s_ready==(!rst && ((spec_count<DEPTH) || (spec_count!=0 && m_ready))));
assign property_payload=rst || spec_count==0 || (output_word[watched_bit]==spec_queue[0]);
assign property_stable=rst || !past_output_held || (m_valid && output_word==past_output);
assign property_capacity=(spec_count<=DEPTH);
always @* begin
 assert(property_valid);assert(property_ready);assert(property_payload);assert(property_stable);assert(property_capacity);
end
endmodule
