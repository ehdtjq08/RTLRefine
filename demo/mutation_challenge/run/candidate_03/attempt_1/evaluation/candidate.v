// SPDX-License-Identifier: MIT
module stream_buffer #(
    ADDR_WIDTH = 2,
    DATA_WIDTH = 8
)(
    input clk,
    input rst,
    input [DATA_WIDTH-1:0] s_data,
    input s_valid,
    output s_ready,
    input s_last,
    input s_user,
    output [DATA_WIDTH-1:0] m_data,
    output m_valid,
    input m_ready,
    output m_last,
    output m_user
);

reg [DATA_WIDTH+1:0] mem [0:(1<<ADDR_WIDTH)-1];
reg [ADDR_WIDTH-1:0] wr_ptr;
reg [ADDR_WIDTH-1:0] rd_ptr;
reg [ADDR_WIDTH:0] count;

assign m_valid = !rst && (count != 0);
assign s_ready = !rst && ((count < (1<<ADDR_WIDTH)) || (m_ready && m_valid));
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
        if (push) wr_ptr <= wr_ptr + 1;
        if (pop) rd_ptr <= rd_ptr + 1;
        case ({push, pop})
            2'b10: count <= count + 1;
            2'b01: count <= count - 1;
            default: count <= count;
        endcase
    end
end
endmodule