// SPDX-License-Identifier: MIT
module stream_buffer #(
    parameter ADDR_WIDTH = 2,
    parameter DATA_WIDTH = 8
)(
    input wire clk,
    input wire rst,
    input wire [DATA_WIDTH-1:0] s_data,
    input wire s_valid,
    output wire s_ready,
    input wire s_last,
    input wire s_user,
    output wire [DATA_WIDTH-1:0] m_data,
    output wire m_valid,
    input wire m_ready,
    output wire m_last,
    output wire m_user
);

localparam DEPTH = 1 << ADDR_WIDTH;
reg [DATA_WIDTH+1:0] mem [0:DEPTH-1];
reg [ADDR_WIDTH-1:0] wr_ptr = 0;
reg [ADDR_WIDTH-1:0] rd_ptr = 0;
reg [ADDR_WIDTH:0] count = 0;

assign m_valid = !rst && (count != 0);
assign s_ready = !rst && ((count < DEPTH) || (m_ready && m_valid));
assign {m_last, m_user, m_data} = mem[rd_ptr];
wire push = s_valid && s_ready;
wire pop = m_valid && m_ready;

always @(posedge clk) begin
    if (rst) begin
        wr_ptr <= 0;
        rd_ptr <= 0;
        count <= 0;
    end else begin
        if (push) begin
            mem[wr_ptr] <= {s_last, s_user, s_data};
        end
        if (push) wr_ptr <= wr_ptr + 1'b1;
        if (pop) rd_ptr <= rd_ptr + 1'b1;
        case ({push, pop})
            2'b10: count <= count + 1'b1;
            2'b01: count <= count - 1'b1;
            default: count <= count;
        endcase
    end
end
endmodule
