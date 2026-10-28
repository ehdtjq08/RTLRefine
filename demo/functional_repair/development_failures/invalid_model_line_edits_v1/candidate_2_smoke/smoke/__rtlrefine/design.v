// RTLRefine independent-property example. MIT; authored defect fixture.
module packet_queue #(parameter WIDTH=4, DEPTH=4)(
    input wire clk, rst,
    input wire s_valid,
    output wire s_ready,
    input wire [WIDTH-1:0] s_data,
    output wire m_valid,
    input wire m_ready,
    output wire [WIDTH-1:0] m_data
);
localparam PW=$clog2(DEPTH);
reg [WIDTH-1:0] memory [0:DEPTH-1];
reg [PW-1:0] write_ptr=0, read_ptr=0;
reg [PW:0] count=0;
wire [PW:0] count_next = count + (push && !pop) - (pop && !push);
assign m_valid = !rst && count_next != 0;
assign s_ready = !rst && (count_next < DEPTH || (m_valid && m_ready));
assign m_data = memory[read_ptr];
wire push = s_valid && s_ready;
wire pop = m_valid && m_ready;
always @(posedge clk) begin
    if (rst) begin
        write_ptr <= 0;
        read_ptr <= 0;
        count <= 0;
    end else begin
        if (push) begin
            memory[write_ptr] <= s_data;
            write_ptr <= write_ptr == DEPTH-1 ? 0 : write_ptr+1;
        end
        if (pop)
            read_ptr <= read_ptr == DEPTH-1 ? 0 : read_ptr+1;
        count <= count_next;
    end
end
endmodule
endmodule
