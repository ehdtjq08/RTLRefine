/*

Copyright (c) 2014 Alex Forencich

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

*/

// Language: Verilog 2001

`timescale 1ns / 1ps

/*
 * AXI4-Stream asynchronous FIFO
 */
module axis_async_fifo #
(
    parameter ADDR_WIDTH = 12,
    parameter DATA_WIDTH = 8
)
(
    /*
     * Common asynchronous reset
     */
    input  wire                   async_rst,

    /*
     * AXI input
     */
    input  wire                   input_clk,
    input  wire [DATA_WIDTH-1:0]  input_axis_tdata,
    input  wire                   input_axis_tvalid,
    output wire                   input_axis_tready,
    input  wire                   input_axis_tlast,
    input  wire                   input_axis_tuser,
    
    /*
     * AXI output
     */
    input  wire                   output_clk,
    output wire [DATA_WIDTH-1:0]  output_axis_tdata,
    output wire                   output_axis_tvalid,
    input  wire                   output_axis_tready,
    output wire                   output_axis_tlast,
    output wire                   output_axis_tuser
);
reg [ADDR_WIDTH:0] wr_ptr = {ADDR_WIDTH+1{1'b0}};
reg [ADDR_WIDTH:0] wr_ptr_next;
reg [ADDR_WIDTH:0] wr_ptr_gray = {ADDR_WIDTH+1{1'b0}};
reg [ADDR_WIDTH:0] rd_ptr = {ADDR_WIDTH+1{1'b0}};
reg [ADDR_WIDTH:0] rd_ptr_next;
reg [ADDR_WIDTH:0] rd_ptr_gray = {ADDR_WIDTH+1{1'b0}};

reg [ADDR_WIDTH:0] wr_ptr_gray_sync1 = {ADDR_WIDTH+1{1'b0}};
reg [ADDR_WIDTH:0] wr_ptr_gray_sync2 = {ADDR_WIDTH+1{1'b0}};
reg [ADDR_WIDTH:0] rd_ptr_gray_sync1 = {ADDR_WIDTH+1{1'b0}};
reg [ADDR_WIDTH:0] rd_ptr_gray_sync2 = {ADDR_WIDTH+1{1'b0}};

reg rst_sync1 = 1;
reg rst_sync2 = 1;
reg rst_sync3 = 1;

reg [DATA_WIDTH+2-1:0] data_out_reg = {1'b0, 1'b0, {DATA_WIDTH{1'b0}}};

reg [DATA_WIDTH+2-1:0] mem[(2**ADDR_WIDTH)-1:0];

reg output_axis_tvalid_reg = 1'b0;

wire [DATA_WIDTH+2-1:0] data_in = {input_axis_tlast, input_axis_tuser, input_axis_tdata};

wire full = ((wr_ptr_gray[ADDR_WIDTH] != rd_ptr_gray_sync2[ADDR_WIDTH]) &&
             (wr_ptr_gray[ADDR_WIDTH-1] != rd_ptr_gray_sync2[ADDR_WIDTH-1]) &&
             (wr_ptr_gray[ADDR_WIDTH-2:0] == rd_ptr_gray_sync2[ADDR_WIDTH-2:0]));

wire empty = rd_ptr_gray == wr_ptr_gray_sync2;

wire write = input_axis_tvalid & ~full;
wire read = (output_axis_tready | ~output_axis_tvalid_reg) & ~empty;

assign {output_axis_tlast, output_axis_tuser, output_axis_tdata} = data_out_reg;

assign input_axis_tready = ~full;
assign output_axis_tvalid = output_axis_tvalid_reg;

assign wr_ptr_next = wr_ptr + 1;
assign rd_ptr_next = rd_ptr + 1;

always @(posedge input_clk) begin
    if (async_rst) begin
        rst_sync1 <= 1;
        rst_sync2 <= 1;
        rst_sync3 <= 1;
    end else begin
        rst_sync1 <= 0;
        rst_sync2 <= rst_sync1;
        rst_sync3 <= rst_sync2;
    end

    if (rst_sync3) begin
        wr_ptr <= 0;
        wr_ptr_gray <= 0;
        rd_ptr <= 0;
        rd_ptr_gray <= 0;
    end else begin
        if (write) begin
            mem[wr_ptr[ADDR_WIDTH-1:0]] <= data_in;
            wr_ptr <= wr_ptr_next;
            wr_ptr_gray <= wr_ptr_next ^ (wr_ptr_next >> 1);
        end
        if (read) begin
            data_out_reg <= mem[rd_ptr[ADDR_WIDTH-1:0]];
            rd_ptr <= rd_ptr_next;
            rd_ptr_gray <= rd_ptr_next ^ (rd_ptr_next >> 1);
        end
    end

    if (rst_sync3) begin
        rd_ptr_gray_sync1 <= 0;
        rd_ptr_gray_sync2 <= 0;
        wr_ptr_gray_sync1 <= 0;
        wr_ptr_gray_sync2 <= 0;
    end else begin
        rd_ptr_gray_sync1 <= rd_ptr_gray;
        rd_ptr_gray_sync2 <= rd_ptr_gray_sync1;
        wr_ptr_gray_sync1 <= wr_ptr_gray;
        wr_ptr_gray_sync2 <= wr_ptr_gray_sync1;
    end

    if (rst_sync3) begin
        output_axis_tvalid_reg <= 1'b0;
    end else if (output_axis_tready | ~output_axis_tvalid_reg) begin
        output_axis_tvalid_reg <= ~empty;
    end
end

endmodule
