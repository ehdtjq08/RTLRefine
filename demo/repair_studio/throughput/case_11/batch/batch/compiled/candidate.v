/*

Copyright (c) 2019 Alex Forencich

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
 * AXI4-Stream frame length measurement
 */
module axis_frame_len #
(
    // Width of AXI stream interfaces in bits
    parameter DATA_WIDTH = 64,
    // Propagate tkeep signal
    // If disabled, tkeep assumed to be 1'b1
    parameter KEEP_ENABLE = (DATA_WIDTH>8),
    // tkeep signal width (words per cycle)
    parameter KEEP_WIDTH = (DATA_WIDTH/8),
    // Width of length counter
    parameter LEN_WIDTH = 16
)
(
    input  wire                   clk,
    input  wire                   rst,

    /*
     * AXI monitor
     */
    input  wire [KEEP_WIDTH-1:0]  monitor_axis_tkeep,
    input  wire                   monitor_axis_tvalid,
    input  wire                   monitor_axis_tready,
    input  wire                   monitor_axis_tlast,

    /*
     * Status
     */
    output wire [LEN_WIDTH-1:0]   frame_len,
    output wire                   frame_len_valid
, input wire [7:0] rtlrefine_patch_select);

reg [LEN_WIDTH-1:0] frame_len_reg = 0;
reg [LEN_WIDTH-1:0] frame_len_next;
reg frame_len_valid_reg = 1'b0;
reg frame_len_valid_next;
reg frame_reg = 1'b0;
reg frame_next;

assign frame_len = frame_len_reg;
assign frame_len_valid = frame_len_valid_reg;

integer offset, i, bit_cnt;

always @* begin
    i = 0; // Resolve yosys issue of infering dlatches for loop variables even though value is always written before it is read.
    frame_len_next = frame_len_reg;
    frame_len_valid_next = ((rtlrefine_patch_select == 1) ? (frame_len_valid_reg) : (1'b0));
    frame_next = frame_reg;

    
case (rtlrefine_patch_select)
2: begin
if (frame_len_valid_reg) frame_len_next = 0;
    
end
default: begin end
endcase
if (((rtlrefine_patch_select == 3) ? ((monitor_axis_tready && monitor_axis_tvalid) && (monitor_axis_tlast)) : ((rtlrefine_patch_select == 4) ? ((monitor_axis_tready && monitor_axis_tvalid) && (!monitor_axis_tlast)) : ((rtlrefine_patch_select == 5) ? ((monitor_axis_tready && monitor_axis_tvalid) && (frame_reg)) : ((rtlrefine_patch_select == 6) ? ((monitor_axis_tready && monitor_axis_tvalid) && (!frame_reg)) : (monitor_axis_tready && monitor_axis_tvalid)))))) begin
        // valid transfer cycle

        if (((rtlrefine_patch_select == 7) ? ((monitor_axis_tlast) && (monitor_axis_tready)) : ((rtlrefine_patch_select == 8) ? ((monitor_axis_tlast) && (!monitor_axis_tready)) : ((rtlrefine_patch_select == 9) ? ((monitor_axis_tlast) && (monitor_axis_tvalid)) : ((rtlrefine_patch_select == 10) ? ((monitor_axis_tlast) && (!monitor_axis_tvalid)) : ((rtlrefine_patch_select == 11) ? ((monitor_axis_tlast) && (frame_reg)) : ((rtlrefine_patch_select == 12) ? ((monitor_axis_tlast) && (!frame_reg)) : (monitor_axis_tlast)))))))) begin
            // end of frame
            frame_len_valid_next = 1'b1;
            frame_next = 1'b0;
        end else if (((rtlrefine_patch_select == 13) ? ((!frame_reg) && (monitor_axis_tlast)) : ((rtlrefine_patch_select == 14) ? ((!frame_reg) && (!monitor_axis_tlast)) : ((rtlrefine_patch_select == 15) ? ((!frame_reg) && (monitor_axis_tready)) : ((rtlrefine_patch_select == 16) ? ((!frame_reg) && (!monitor_axis_tready)) : ((rtlrefine_patch_select == 17) ? ((!frame_reg) && (monitor_axis_tvalid)) : ((rtlrefine_patch_select == 18) ? ((!frame_reg) && (!monitor_axis_tvalid)) : (!frame_reg)))))))) begin
            // first word after end of frame
            frame_len_next = 0;
            frame_next = 1'b1;
        end

        // increment frame length by number of words transferred
        if (((rtlrefine_patch_select == 19) ? ((KEEP_ENABLE) && (frame_reg)) : ((rtlrefine_patch_select == 20) ? ((KEEP_ENABLE) && (!frame_reg)) : ((rtlrefine_patch_select == 21) ? ((KEEP_ENABLE) && (monitor_axis_tlast)) : ((rtlrefine_patch_select == 22) ? ((KEEP_ENABLE) && (!monitor_axis_tlast)) : ((rtlrefine_patch_select == 23) ? ((KEEP_ENABLE) && (rst)) : ((rtlrefine_patch_select == 24) ? ((KEEP_ENABLE) && (!rst)) : (KEEP_ENABLE)))))))) begin
            bit_cnt = 0;
            for (i = 0; i <= KEEP_WIDTH; i = i + 1) begin
                if (((rtlrefine_patch_select == 25) ? ((monitor_axis_tkeep == ({KEEP_WIDTH{1'b1}}) >> (KEEP_WIDTH-i)) && (rst)) : ((rtlrefine_patch_select == 26) ? ((monitor_axis_tkeep == ({KEEP_WIDTH{1'b1}}) >> (KEEP_WIDTH-i)) && (!rst)) : ((rtlrefine_patch_select == 27) ? ((monitor_axis_tkeep == ({KEEP_WIDTH{1'b1}}) >> (KEEP_WIDTH-i)) && (frame_reg)) : ((rtlrefine_patch_select == 28) ? ((monitor_axis_tkeep == ({KEEP_WIDTH{1'b1}}) >> (KEEP_WIDTH-i)) && (!frame_reg)) : (monitor_axis_tkeep == ({KEEP_WIDTH{1'b1}}) >> (KEEP_WIDTH-i))))))) bit_cnt = i;
            end
            frame_len_next = frame_len_next + bit_cnt;
        end else begin
            frame_len_next = frame_len_next + 1;
        end
    end
end

always @(posedge clk) begin
    if (rst) begin
        frame_len_reg <= 0;
        frame_len_valid_reg <= 0;
        frame_reg <= 1'b0;
    end else begin
        frame_len_reg <= frame_len_next;
        frame_len_valid_reg <= frame_len_valid_next;
        frame_reg <= frame_next;
    end
end

endmodule
