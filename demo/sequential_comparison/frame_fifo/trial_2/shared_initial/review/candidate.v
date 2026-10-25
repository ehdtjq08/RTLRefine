```systemverilog

module axis_async_fifo #
(
    parameter int DATA_WIDTH = 8,
    parameter int ID_WIDTH = 1,
    parameter int DEST_WIDTH = 1,
    parameter int USER_WIDTH = 1,
    parameter int DEPTH = 4,
    parameter bit OUTPUT_REG = 1
)
(
    input logic clk,
    input logic rst,
    /*
     * AXI Stream Slave Interface
     */
    input logic s_valid,
    output logic s_ready,
    input logic [DATA_WIDTH-1:0] s_data,
    input logic [ID_WIDTH-1:0] s_id,
    input logic [DEST_WIDTH-1:0] s_dest,
    input logic [USER_WIDTH-1:0] s_user,
    /*
     * AXI Stream Master Interface
     */
    output logic m_valid,
    input logic m_ready,
    output logic [DATA_WIDTH-1:0] m_data,
    output logic [ID_WIDTH-1:0] m_id,
    output logic [DEST_WIDTH-1:0] m_dest,
    output logic [USER_WIDTH-1:0] m_user
);

    localparam int ADDR_WIDTH = $clog2(DEPTH);
    localparam int COUNT_WIDTH = ADDR_WIDTH + 1;

    logic [DATA_WIDTH-1:0] data_mem [DEPTH-1:0];
    logic [ID_WIDTH-1:0] id_mem [DEPTH-1:0];
    logic [DEST_WIDTH-1:0] dest_mem [DEPTH-1:0];
    logic [USER_WIDTH-1:0] user_mem [DEPTH-1:0];

    logic [COUNT_WIDTH-1:0] wr_ptr, wr_ptr_next;
    logic [COUNT_WIDTH-1:0] rd_ptr, rd_ptr_next;

    logic full;
    logic empty;

    logic mem_wr_en;
    logic mem_rd_en;

    logic output_reg;
    logic [DATA_WIDTH-1:0] output_data_reg;
    logic [ID_WIDTH-1:0] output_id_reg;
    logic [DEST_WIDTH-1:0] output_dest_reg;
    logic [USER_WIDTH-1:0] output_user_reg;

    logic output_reg_next;
    logic [DATA_WIDTH-1:0] output_data_reg_next;
    logic [ID_WIDTH-1:0] output_id_reg_next;
    logic [DEST_WIDTH-1:0] output_dest_reg_next;
    logic [USER_WIDTH-1:0] output_user_reg_next;

    assign full = (wr_ptr[ADDR_WIDTH] != rd_ptr[ADDR_WIDTH]) && (wr_ptr[ADDR_WIDTH-1:0] == rd_ptr[ADDR_WIDTH-1:0]);
    assign empty = (wr_ptr == rd_ptr);

    assign mem_wr_en = s_valid & s_ready & ~full;
    assign mem_rd_en = (~empty & m_ready & ~output_reg) | (output_reg & m_ready);

    assign s_ready = ~full | (output_reg & m_ready & empty);
    assign m_valid = ~empty | output_reg;

    assign m_data = output_data_reg;
    assign m_id = output_id_reg;
    assign m_dest = output_dest_reg;
    assign m_user = output_user_reg;

    // Memory write
    always_comb begin
        if (mem_wr_en) begin
            data_mem[wr_ptr[ADDR_WIDTH-1:0]] = s_data;
            id_mem[wr_ptr[ADDR_WIDTH-1:0]] = s_id;
            dest_mem[wr_ptr[ADDR_WIDTH-1:0]] = s_dest;
            user_mem[wr_ptr[ADDR_WIDTH-1:0]] = s_user;
        end
    end

    // Memory read address
    logic [ADDR_WIDTH-1:0] mem_rd_addr;
    assign mem_rd_addr = rd_ptr[ADDR_WIDTH-1:0];

    // Next state logic
    always_comb begin
        // Pointer updates
        wr_ptr_next = wr_ptr;
        rd_ptr_next = rd_ptr;
        if (mem_wr_en)
            wr_ptr_next = wr_ptr + 1;
        if (mem_rd_en)
            rd_ptr_next = rd_ptr + 1;

        // Output register
        output_reg_next = output_reg;
        output_data_reg_next = output_data_reg;
        output_id_reg_next = output_id_reg;
        output_dest_reg_next = output_dest_reg;
        output_user_reg_next = output_user_reg;

        if (mem_rd_en & ~output_reg) begin
            output_reg_next = 1'b1;
            output_data_reg_next = data_mem[mem_rd_addr];
            output_id_reg_next = id_mem[mem_rd_addr];
            output_dest_reg_next = dest_mem[mem_rd_addr];
            output_user_reg_next = user_mem[mem_rd_addr];
        end else if (output_reg & m_ready) begin
            output_reg_next = 1'b0;
        end

        if (rst) begin
            wr_ptr_next = '0;
            rd_ptr_next = '0;
            output_reg_next = 1'b0;
        end
    end

    always_ff @(posedge clk) begin
        wr_ptr <= wr_ptr_next;
        rd_ptr <= rd_ptr_next;
        output_reg <= output_reg_next;
        output_data_reg <= output_data_reg_next;
        output_id_reg <= output_id_reg_next;
        output_dest_reg <= output_dest_reg_next;
        output_user_reg <= output_user_reg_next;
    end

endmodule

```