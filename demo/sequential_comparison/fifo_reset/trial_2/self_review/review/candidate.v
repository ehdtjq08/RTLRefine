module axis_async_fifo_adapter #(
    parameter int ADDR_WIDTH = 12,
    parameter int DATA_WIDTH = 8,
    parameter string INPUT_CLK_DOMAIN = "input_clk",
    parameter string OUTPUT_CLK_DOMAIN = "output_clk"
)
(
    input  logic                      input_clk,
    input  logic                      input_rst,
    input  logic                      output_clk,
    input  logic                      output_rst,
    // AXI Stream Input
    input  logic                      input_axis_tvalid,
    output logic                      input_axis_tready,
    input  logic [DATA_WIDTH-1:0]     input_axis_tdata,
    // AXI Stream Output
    output logic                      output_axis_tvalid,
    input  logic                      output_axis_tready,
    output logic [DATA_WIDTH-1:0]     output_axis_tdata
);

    localparam int FULL_ADDR_WIDTH = ADDR_WIDTH + 1;
    localparam int WORDS = 1 << ADDR_WIDTH;

    // Memory
    logic [DATA_WIDTH-1:0] mem [0:WORDS-1];

    // Write pointer (binary and gray)
    logic [ADDR_WIDTH:0] wr_ptr;
    logic [ADDR_WIDTH:0] wr_ptr_gray;
    logic [ADDR_WIDTH:0] wr_ptr_next;
    logic [ADDR_WIDTH:0] wr_ptr_gray_next;
    logic write;

    // Read pointer (binary and gray)
    logic [ADDR_WIDTH:0] rd_ptr;
    logic [ADDR_WIDTH:0] rd_ptr_gray;
    logic [ADDR_WIDTH:0] rd_ptr_next;
    logic [ADDR_WIDTH:0] rd_ptr_gray_next;
    logic read;

    // Synchronized pointers
    logic [ADDR_WIDTH:0] wr_ptr_gray_sync1, wr_ptr_gray_sync2;
    logic [ADDR_WIDTH:0] rd_ptr_gray_sync1, rd_ptr_gray_sync2;

    // Status
    logic full, empty;

    // Input AXI Stream
    assign input_axis_tready = ~full;
    assign write = input_axis_tvalid & input_axis_tready;

    // Output AXI Stream
    logic [DATA_WIDTH-1:0] data_out_reg;
    logic output_axis_tvalid_reg;
    assign output_axis_tdata = data_out_reg;
    assign output_axis_tvalid = output_axis_tvalid_reg;
    assign read = output_axis_tvalid & output_axis_tready;

    // Gray coding functions
    function automatic logic [ADDR_WIDTH:0] bin2gray(input logic [ADDR_WIDTH:0] bin);
        return bin ^ (bin >> 1);
    endfunction

    function automatic logic [ADDR_WIDTH:0] gray2bin(input logic [ADDR_WIDTH:0] gray);
        logic [ADDR_WIDTH:0] bin;
        integer i;
        bin[ADDR_WIDTH] = gray[ADDR_WIDTH];
        for (i = ADDR_WIDTH-1; i >= 0; i--) begin
            bin[i] = bin[i+1] ^ gray[i];
        end
        return bin;
    endfunction

    // Next pointer calculations
    assign wr_ptr_next = wr_ptr + 1'b1;
    assign wr_ptr_gray_next = bin2gray(wr_ptr_next);
    assign rd_ptr_next = rd_ptr + 1'b1;
    assign rd_ptr_gray_next = bin2gray(rd_ptr_next);

    // Status flags using synchronized gray pointers
    logic [ADDR_WIDTH:0] wr_ptr_gray_sync2_bin, rd_ptr_gray_sync2_bin;
    assign wr_ptr_gray_sync2_bin = gray2bin(wr_ptr_gray_sync2);
    assign rd_ptr_gray_sync2_bin = gray2bin(rd_ptr_gray_sync2);

    assign full = (wr_ptr_gray_next == rd_ptr_gray_sync2);
    assign empty = (rd_ptr_gray == wr_ptr_gray_sync2);

    // ------------------------------------------------------------
    // Reset Synchronization
    // ------------------------------------------------------------
    logic input_rst_sync1, input_rst_sync2;
    logic output_rst_sync1, output_rst_sync2;
    logic input_rst_combined, output_rst_combined;

    // Synchronize output_rst into input_clk domain
    always_ff @(posedge input_clk or posedge input_rst) begin
        if (input_rst) begin
            output_rst_sync1 <= 1'b1;
            output_rst_sync2 <= 1'b1;
        end else begin
            output_rst_sync1 <= output_rst;
            output_rst_sync2 <= output_rst_sync1;
        end
    end
    assign input_rst_combined = input_rst | output_rst_sync2;

    // Synchronize input_rst into output_clk domain
    always_ff @(posedge output_clk or posedge output_rst) begin
        if (output_rst) begin
            input_rst_sync1 <= 1'b1;
            input_rst_sync2 <= 1'b1;
        end else begin
            input_rst_sync1 <= input_rst;
            input_rst_sync2 <= input_rst_sync1;
        end
    end
    assign output_rst_combined = output_rst | input_rst_sync2;

    // ------------------------------------------------------------
    // Write Domain Logic (input_clk)
    // ------------------------------------------------------------
    always_ff @(posedge input_clk or posedge input_rst_combined) begin
        if (input_rst_combined) begin
            wr_ptr <= '0;
            wr_ptr_gray <= '0;
        end else if (write) begin
            mem[wr_ptr[ADDR_WIDTH-1:0]] <= input_axis_tdata;
            wr_ptr <= wr_ptr_next;
            wr_ptr_gray <= wr_ptr_gray_next;
        end
    end

    // Synchronize rd_ptr_gray into input_clk domain
    always_ff @(posedge input_clk or posedge input_rst_combined) begin
        if (input_rst_combined) begin
            rd_ptr_gray_sync1 <= '0;
            rd_ptr_gray_sync2 <= '0;
        end else begin
            rd_ptr_gray_sync1 <= rd_ptr_gray;
            rd_ptr_gray_sync2 <= rd_ptr_gray_sync1;
        end
    end

    // ------------------------------------------------------------
    // Read Domain Logic (output_clk)
    // ------------------------------------------------------------
    always_ff @(posedge output_clk or posedge output_rst_combined) begin
        if (output_rst_combined) begin
            rd_ptr <= '0;
            rd_ptr_gray <= '0;
        end else if (read) begin
            data_out_reg <= mem[rd_ptr[ADDR_WIDTH-1:0]];
            rd_ptr <= rd_ptr_next;
            rd_ptr_gray <= rd_ptr_gray_next;
        end
    end

    // Synchronize wr_ptr_gray into output_clk domain
    always_ff @(posedge output_clk or posedge output_rst_combined) begin
        if (output_rst_combined) begin
            wr_ptr_gray_sync1 <= '0;
            wr_ptr_gray_sync2 <= '0;
        end else begin
            wr_ptr_gray_sync1 <= wr_ptr_gray;
            wr_ptr_gray_sync2 <= wr_ptr_gray_sync1;
        end
    end

    // Output valid signal generation
    always_ff @(posedge output_clk or posedge output_rst_combined) begin
        if (output_rst_combined) begin
            output_axis_tvalid_reg <= 1'b0;
        end else if (output_axis_tready || ~output_axis_tvalid_reg) begin
            output_axis_tvalid_reg <= ~empty;
        end
    end

endmodule