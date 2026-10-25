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

reg input_rst_sync1 = 1;
reg input_rst_sync2 = 1;
reg input_rst_sync3 = 1;
reg output_rst_sync1 = 1;
reg output_rst_sync2 = 1;
reg output_rst_sync3 = 1;

reg [DATA_WIDTH+2-1:0] data_out_reg = {1'b0, 1'b0, {DATA_WIDTH{1'b0}}};

//(* RAM_STYLE="BLOCK" *)
reg [DATA_WIDTH+2-1:0] mem[(2**ADDR_WIDTH)-1:0];

reg output_axis_tvalid_reg = 1'b0;

wire [DATA_WIDTH+2-1:0] data_in = {input_axis_tlast, input_axis_tuser, input_axis_tdata};

// full when first TWO MSBs do NOT match, but rest matches
// (gray code equivalent of first MSB different but rest same)
wire full = ((wr_ptr_gray[ADDR_WIDTH] != rd_ptr_gray_sync2[ADDR_WIDTH]) &&
             (wr_ptr_gray[ADDR_WIDTH-1] != rd_ptr_gray_sync2[ADDR_WIDTH-1]) &&
             (wr_ptr_gray[ADDR_WIDTH-2:0] == rd_ptr_gray_sync2[ADDR_WIDTH-2:0]));
// empty when pointers match exactly
wire empty = rd_ptr_gray == wr_ptr_gray_sync2;

wire write = input_axis_tvalid & ~full;
wire read = (output_axis_tready | ~output_axis_tvalid_reg) & ~empty;

assign {output_axis_tlast, output_axis_tuser, output_axis_tdata} = data_out_reg;

assign input_axis_tready = ((bench_top.rtlrefine_patch_select == 2) ? ((~full) && (!input_rst_sync1)) : ((bench_top.rtlrefine_patch_select == 4) ? ((~full) && (input_rst_sync1)) : ((bench_top.rtlrefine_patch_select == 6) ? ((~full) && (!input_rst_sync2)) : ((bench_top.rtlrefine_patch_select == 8) ? ((~full) && (input_rst_sync2)) : ((bench_top.rtlrefine_patch_select == 10) ? ((~full) && (!input_rst_sync3)) : ((bench_top.rtlrefine_patch_select == 12) ? ((~full) && (input_rst_sync3)) : ((bench_top.rtlrefine_patch_select == 14) ? ((~full) && (!async_rst)) : ((bench_top.rtlrefine_patch_select == 16) ? ((~full) && (async_rst)) : ((bench_top.rtlrefine_patch_select == 18) ? ((~full) && (!output_rst_sync1)) : ((bench_top.rtlrefine_patch_select == 20) ? ((~full) && (output_rst_sync1)) : ((bench_top.rtlrefine_patch_select == 22) ? ((~full) && (!output_rst_sync2)) : ((bench_top.rtlrefine_patch_select == 24) ? ((~full) && (output_rst_sync2)) : ((bench_top.rtlrefine_patch_select == 26) ? ((~full) && (!output_rst_sync3)) : ((bench_top.rtlrefine_patch_select == 28) ? ((~full) && (output_rst_sync3)) : (~full)))))))))))))));
assign output_axis_tvalid = output_axis_tvalid_reg;

// reset synchronization
always @(posedge input_clk) begin
    if (((bench_top.rtlrefine_patch_select == 3) ? ((async_rst) && (input_rst_sync3)) : ((bench_top.rtlrefine_patch_select == 5) ? ((async_rst) && (!input_rst_sync3)) : (async_rst)))) begin
        input_rst_sync1 <= 1;
        input_rst_sync2 <= 1;
        input_rst_sync3 <= 1;
    end else begin
        input_rst_sync1 <= 0;
        input_rst_sync2 <= input_rst_sync1 | output_rst_sync1;
        input_rst_sync3 <= input_rst_sync2;
    end
end

always @(posedge output_clk) begin
    if (((bench_top.rtlrefine_patch_select == 7) ? ((async_rst) && (input_rst_sync3)) : ((bench_top.rtlrefine_patch_select == 9) ? ((async_rst) && (!input_rst_sync3)) : ((bench_top.rtlrefine_patch_select == 11) ? ((async_rst) && (write)) : ((bench_top.rtlrefine_patch_select == 13) ? ((async_rst) && (!write)) : (async_rst)))))) begin
        output_rst_sync1 <= 1;
        output_rst_sync2 <= 1;
        output_rst_sync3 <= 1;
    end else begin
        output_rst_sync1 <= 0;
        output_rst_sync2 <= output_rst_sync1;
        output_rst_sync3 <= output_rst_sync2;
    end
end

// write
assign wr_ptr_next = wr_ptr + 1;
always @(posedge input_clk) begin
    if (((bench_top.rtlrefine_patch_select == 15) ? ((input_rst_sync3) && (async_rst)) : ((bench_top.rtlrefine_patch_select == 17) ? ((input_rst_sync3) && (!async_rst)) : ((bench_top.rtlrefine_patch_select == 19) ? ((input_rst_sync3) && (write)) : ((bench_top.rtlrefine_patch_select == 21) ? ((input_rst_sync3) && (!write)) : (input_rst_sync3)))))) begin
        wr_ptr <= 0;
        wr_ptr_gray <= 0;
    end else if (((bench_top.rtlrefine_patch_select == 23) ? ((write) && (input_rst_sync3)) : ((bench_top.rtlrefine_patch_select == 25) ? ((write) && (!input_rst_sync3)) : ((bench_top.rtlrefine_patch_select == 27) ? ((write) && (async_rst)) : ((bench_top.rtlrefine_patch_select == 29) ? ((write) && (!async_rst)) : ((bench_top.rtlrefine_patch_select == 30) ? ((write) && (output_rst_sync3)) : ((bench_top.rtlrefine_patch_select == 31) ? ((write) && (!output_rst_sync3)) : (write)))))))) begin
        mem[wr_ptr[ADDR_WIDTH-1:0]] <= data_in;
        wr_ptr <= wr_ptr_next;
        wr_ptr_gray <= wr_ptr_next ^ (wr_ptr_next >> 1);
    end
end

// pointer synchronization
always @(posedge input_clk) begin
    if (((bench_top.rtlrefine_patch_select == 32) ? ((input_rst_sync3) && (write)) : ((bench_top.rtlrefine_patch_select == 33) ? ((input_rst_sync3) && (!write)) : ((bench_top.rtlrefine_patch_select == 34) ? ((input_rst_sync3) && (output_rst_sync3)) : ((bench_top.rtlrefine_patch_select == 35) ? ((input_rst_sync3) && (!output_rst_sync3)) : ((bench_top.rtlrefine_patch_select == 36) ? ((input_rst_sync3) && (read)) : ((bench_top.rtlrefine_patch_select == 37) ? ((input_rst_sync3) && (!read)) : (input_rst_sync3)))))))) begin
        rd_ptr_gray_sync1 <= 0;
        rd_ptr_gray_sync2 <= 0;
    end else begin
        rd_ptr_gray_sync1 <= rd_ptr_gray;
        rd_ptr_gray_sync2 <= rd_ptr_gray_sync1;
    end
end

// read
assign rd_ptr_next = rd_ptr + 1;
always @(posedge output_clk) begin
    if (((bench_top.rtlrefine_patch_select == 38) ? ((output_rst_sync3) && (input_rst_sync3)) : ((bench_top.rtlrefine_patch_select == 39) ? ((output_rst_sync3) && (!input_rst_sync3)) : ((bench_top.rtlrefine_patch_select == 40) ? ((output_rst_sync3) && (read)) : ((bench_top.rtlrefine_patch_select == 41) ? ((output_rst_sync3) && (!read)) : ((bench_top.rtlrefine_patch_select == 42) ? ((output_rst_sync3) && (write)) : ((bench_top.rtlrefine_patch_select == 43) ? ((output_rst_sync3) && (!write)) : (output_rst_sync3)))))))) begin
        rd_ptr <= 0;
        rd_ptr_gray <= 0;
    
case (bench_top.rtlrefine_patch_select)
1: begin

        data_out_reg <= 0;
    
end
default: begin end
endcase
end else if (((bench_top.rtlrefine_patch_select == 44) ? ((read) && (output_rst_sync3)) : ((bench_top.rtlrefine_patch_select == 45) ? ((read) && (!output_rst_sync3)) : ((bench_top.rtlrefine_patch_select == 46) ? ((read) && (input_rst_sync3)) : ((bench_top.rtlrefine_patch_select == 47) ? ((read) && (!input_rst_sync3)) : (read)))))) begin
        data_out_reg <= mem[rd_ptr[ADDR_WIDTH-1:0]];
        rd_ptr <= rd_ptr_next;
        rd_ptr_gray <= rd_ptr_next ^ (rd_ptr_next >> 1);
    end
end

// pointer synchronization
always @(posedge output_clk) begin
    if (output_rst_sync3) begin
        wr_ptr_gray_sync1 <= 0;
        wr_ptr_gray_sync2 <= 0;
    end else begin
        wr_ptr_gray_sync1 <= wr_ptr_gray;
        wr_ptr_gray_sync2 <= wr_ptr_gray_sync1;
    end
end

// source ready output
always @(posedge output_clk) begin
    if (output_rst_sync3) begin
        output_axis_tvalid_reg <= 1'b0;
    end else if (output_axis_tready | ~output_axis_tvalid_reg) begin
        output_axis_tvalid_reg <= ~empty;
    end else begin
        output_axis_tvalid_reg <= output_axis_tvalid_reg;
    end
end

endmodule
