module packet_fifo #(
    parameter DEPTH = 32,
    parameter DATA_WIDTH = 8,
    parameter USER_WIDTH = 1,
    parameter DEST_WIDTH = 2,
    parameter ID_WIDTH = 2
)(
    input logic clk,
    input logic rst,
    
    input logic [DATA_WIDTH-1:0] data_in,
    input logic [USER_WIDTH-1:0] user_in,
    input logic [DEST_WIDTH-1:0] dest_in,
    input logic [ID_WIDTH-1:0] id_in,
    input logic sop_in,
    input logic eop_in,
    input logic valid_in,
    output logic ready_in,
    
    output logic [DATA_WIDTH-1:0] data_out,
    output logic [USER_WIDTH-1:0] user_out,
    output logic [DEST_WIDTH-1:0] dest_out,
    output logic [ID_WIDTH-1:0] id_out,
    output logic sop_out,
    output logic eop_out,
    output logic valid_out,
    input logic ready_out
);

    localparam DEPTH_BITS = $clog2(DEPTH);

    logic [DATA_WIDTH-1:0] data_mem [DEPTH-1:0];
    logic [USER_WIDTH-1:0] user_mem [DEPTH-1:0];
    logic [DEST_WIDTH-1:0] dest_mem [DEPTH-1:0];
    logic [ID_WIDTH-1:0] id_mem [DEPTH-1:0];
    logic sop_mem [DEPTH-1:0];
    logic eop_mem [DEPTH-1:0];
    logic valid_mem [DEPTH-1:0];

    logic [DEPTH_BITS:0] count = 0;
    logic [DEPTH_BITS-1:0] head = 0;
    logic [DEPTH_BITS-1:0] tail = 0;

    logic write_en;
    logic read_en;

    assign write_en = valid_in & ready_in;
    assign read_en = valid_out & ready_out;

    assign ready_in = (count < DEPTH);
    assign valid_out = (count > 0);

    assign data_out = data_mem[head];
    assign user_out = user_mem[head];
    assign dest_out = dest_mem[head];
    assign id_out = id_mem[head];
    assign sop_out = sop_mem[head];
    assign eop_out = eop_mem[head];

    always @(posedge clk) begin
        if (write_en) begin
            data_mem[tail] <= data_in;
            user_mem[tail] <= user_in;
            dest_mem[tail] <= dest_in;
            id_mem[tail] <= id_in;
            sop_mem[tail] <= sop_in;
            eop_mem[tail] <= eop_in;
            valid_mem[tail] <= 1'b1;
            tail <= tail + 1'b1;
        end

        if (read_en) begin
            valid_mem[head] <= 1'b0;
            head <= head + 1'b1;
        end

        case ({write_en, read_en})
            2'b10: count <= count + 1'b1;
            2'b01: count <= count - 1'b1;
            default: count <= count;
        endcase

        if (rst) begin
            count <= 0;
            head <= 0;
            tail <= 0;
            for (int i = 0; i < DEPTH; i++) begin
                valid_mem[i] <= 1'b0;
            end
        end
    end
endmodule

// Top-level module that matches the expected interface (if needed)
module axis_packet_fifo #(
    parameter DEPTH = 32,
    parameter DATA_WIDTH = 8,
    parameter USER_WIDTH = 1,
    parameter DEST_WIDTH = 2,
    parameter ID_WIDTH = 2
)(
    input logic clk,
    input logic rst,
    
    input logic [DATA_WIDTH-1:0] s_axis_tdata,
    input logic [USER_WIDTH-1:0] s_axis_tuser,
    input logic [DEST_WIDTH-1:0] s_axis_tdest,
    input logic [ID_WIDTH-1:0] s_axis_tid,
    input logic s_axis_tsop,
    input logic s_axis_teop,
    input logic s_axis_tvalid,
    output logic s_axis_tready,
    
    output logic [DATA_WIDTH-1:0] m_axis_tdata,
    output logic [USER_WIDTH-1:0] m_axis_tuser,
    output logic [DEST_WIDTH-1:0] m_axis_tdest,
    output logic [ID_WIDTH-1:0] m_axis_tid,
    output logic m_axis_tsop,
    output logic m_axis_teop,
    output logic m_axis_tvalid,
    input logic m_axis_tready
);

    packet_fifo #(
        .DEPTH(DEPTH),
        .DATA_WIDTH(DATA_WIDTH),
        .USER_WIDTH(USER_WIDTH),
        .DEST_WIDTH(DEST_WIDTH),
        .ID_WIDTH(ID_WIDTH)
    ) fifo_inst (
        .clk(clk),
        .rst(rst),
        .data_in(s_axis_tdata),
        .user_in(s_axis_tuser),
        .dest_in(s_axis_tdest),
        .id_in(s_axis_tid),
        .sop_in(s_axis_tsop),
        .eop_in(s_axis_teop),
        .valid_in(s_axis_tvalid),
        .ready_in(s_axis_tready),
        .data_out(m_axis_tdata),
        .user_out(m_axis_tuser),
        .dest_out(m_axis_tdest),
        .id_out(m_axis_tid),
        .sop_out(m_axis_tsop),
        .eop_out(m_axis_teop),
        .valid_out(m_axis_tvalid),
        .ready_out(m_axis_tready)
    );
endmodule