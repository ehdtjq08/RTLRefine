module axis_fifo #(
    parameter int DATA_WIDTH = 8,
    parameter int ADDR_WIDTH = 4,
    parameter int DEPTH = 2 ** ADDR_WIDTH,
    parameter int ID_WIDTH = 8,
    parameter int DEST_WIDTH = 8,
    parameter int USER_WIDTH = 1,
    parameter int USER_ID = 0,
    parameter int DEST_ID = 0,
    parameter int USER_WIDTH_ADJ = 0
)(
    input logic clk,
    input logic rst,
    
    input logic [DATA_WIDTH-1:0] input_axis_tdata,
    input logic [ID_WIDTH-1:0] input_axis_tid,
    input logic [DEST_WIDTH-1:0] input_axis_tdest,
    input logic [USER_WIDTH-1:0] input_axis_tuser,
    input logic input_axis_tvalid,
    output logic input_axis_tready,
    
    output logic [DATA_WIDTH-1:0] output_axis_tdata,
    output logic [ID_WIDTH-1:0] output_axis_tid,
    output logic [DEST_WIDTH-1:0] output_axis_tdest,
    output logic [USER_WIDTH-1:0] output_axis_tuser,
    output logic output_axis_tvalid,
    input logic output_axis_tready
);

    function automatic [ADDR_WIDTH:0] bin2gray(input logic [ADDR_WIDTH:0] bin);
    function automatic [ADDR_WIDTH:0] gray2bin(input logic [ADDR_WIDTH:0] gray);

    logic [DATA_WIDTH+ID_WIDTH+DEST_WIDTH+USER_WIDTH-1:0] mem [DEPTH-1:0];

    logic [ADDR_WIDTH:0] wr_ptr_gray_reg, wr_ptr_gray_next;
    logic [ADDR_WIDTH:0] rd_ptr_gray_reg, rd_ptr_gray_next;
    logic [ADDR_WIDTH-1:0] wr_ptr_bin_reg, wr_ptr_bin_next;
    logic [ADDR_WIDTH-1:0] rd_ptr_bin_reg, rd_ptr_bin_next;

    logic [ADDR_WIDTH:0] wr_ptr_gray_sync1_reg, wr_ptr_gray_sync2_reg;
    logic [ADDR_WIDTH:0] rd_ptr_gray_sync1_reg, rd_ptr_gray_sync2_reg;
    logic [ADDR_WIDTH-1:0] wr_ptr_bin_sync2_reg, rd_ptr_bin_sync2_reg;

    logic full, empty;

    logic output_axis_tvalid_reg;

    assign input_axis_tready = ~full;
    assign output_axis_tvalid = output_axis_tvalid_reg;

    assign {output_axis_tdata, output_axis_tid, output_axis_tdest, output_axis_tuser} = output_axis_tvalid_reg ? mem[rd_ptr_bin_reg] : '0;

    always_comb begin
        wr_ptr_bin_next = wr_ptr_bin_reg + 1;
        wr_ptr_gray_next = bin2gray({1'b0, wr_ptr_bin_next});
        rd_ptr_bin_next = rd_ptr_bin_reg + 1;
        rd_ptr_gray_next = bin2gray({1'b0, rd_ptr_bin_next});
    end

    always_comb begin
        for (int i = ADDR_WIDTH; i >= 0; i--) begin
            wr_ptr_bin_sync2_reg[i] = ^wr_ptr_gray_sync2_reg[ADDR_WIDTH:i];
            rd_ptr_bin_sync2_reg[i] = ^rd_ptr_gray_sync2_reg[ADDR_WIDTH:i];
        end
    end

    assign full = (wr_ptr_gray_reg == {~rd_ptr_gray_sync2_reg[ADDR_WIDTH], rd_ptr_gray_sync2_reg[ADDR_WIDTH-1:0]});
    assign empty = (rd_ptr_gray_reg == wr_ptr_gray_sync2_reg);

    always_ff @(posedge clk) begin
        if (rst) begin
            wr_ptr_gray_reg <= '0;
            wr_ptr_bin_reg <= '0;
            wr_ptr_gray_sync1_reg <= '0;
            wr_ptr_gray_sync2_reg <= '0;
            rd_ptr_gray_reg <= '0;
            rd_ptr_bin_reg <= '0;
            rd_ptr_gray_sync1_reg <= '0;
            rd_ptr_gray_sync2_reg <= '0;
            output_axis_tvalid_reg <= 1'b0;
        end else begin
            wr_ptr_gray_sync1_reg <= wr_ptr_gray_reg;
            wr_ptr_gray_sync2_reg <= wr_ptr_gray_sync1_reg;
            rd_ptr_gray_sync1_reg <= rd_ptr_gray_reg;
            rd_ptr_gray_sync2_reg <= rd_ptr_gray_sync1_reg;

            if (input_axis_tvalid & input_axis_tready) begin
                wr_ptr_gray_reg <= wr_ptr_gray_next;
                wr_ptr_bin_reg <= wr_ptr_bin_next;
                mem[wr_ptr_bin_reg] <= {input_axis_tdata, input_axis_tid, input_axis_tdest, input_axis_tuser};
            end

            if (output_axis_tvalid_reg & output_axis_tready) begin
                rd_ptr_gray_reg <= rd_ptr_gray_next;
                rd_ptr_bin_reg <= rd_ptr_bin_next;
            end

            if (output_axis_tready | ~output_axis_tvalid_reg) begin
                output_axis_tvalid_reg <= ~empty;
            end
        end
    end

    function automatic [ADDR_WIDTH:0] bin2gray(input logic [ADDR_WIDTH:0] bin);
        return (bin >> 1) ^ bin;
    endfunction

    function automatic [ADDR_WIDTH:0] gray2bin(input logic [ADDR_WIDTH:0] gray);
        logic [ADDR_WIDTH:0] bin;
        for (int i = ADDR_WIDTH; i >= 0; i--) begin
            bin[i] = ^gray[ADDR_WIDTH:i];
        end
        return bin;
    endfunction

endmodule
