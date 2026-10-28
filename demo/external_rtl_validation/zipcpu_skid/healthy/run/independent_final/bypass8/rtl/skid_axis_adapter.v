/*

Copyright (c) 2014-2018 Alex Forencich

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

`resetall
`timescale 1ns / 1ps
`default_nettype none

/*
 * AXI4-Stream register
 */
module skid_axis_adapter #
(
    // Width of AXI stream interfaces in bits
    parameter DATA_WIDTH = 8,
    // Propagate tkeep signal
    parameter KEEP_ENABLE = (DATA_WIDTH>8),
    // tkeep signal width (words per cycle)
    parameter KEEP_WIDTH = ((DATA_WIDTH+7)/8),
    // Propagate tlast signal
    parameter LAST_ENABLE = 1,
    // Propagate tid signal
    parameter ID_ENABLE = 0,
    // tid signal width
    parameter ID_WIDTH = 8,
    // Propagate tdest signal
    parameter DEST_ENABLE = 0,
    // tdest signal width
    parameter DEST_WIDTH = 8,
    // Propagate tuser signal
    parameter USER_ENABLE = 1,
    // tuser signal width
    parameter USER_WIDTH = 1,
    // Register type
    // 0 to bypass, 1 for simple buffer, 2 for skid buffer
    parameter LOWPOWER = 1,
    parameter REG_TYPE = 2
)
(
    input  wire                   clk,
    input  wire                   rst,

    /*
     * AXI Stream input
     */
    input  wire [DATA_WIDTH-1:0]  s_axis_tdata,
    input  wire [KEEP_WIDTH-1:0]  s_axis_tkeep,
    input  wire                   s_axis_tvalid,
    output wire                   s_axis_tready,
    input  wire                   s_axis_tlast,
    input  wire [ID_WIDTH-1:0]    s_axis_tid,
    input  wire [DEST_WIDTH-1:0]  s_axis_tdest,
    input  wire [USER_WIDTH-1:0]  s_axis_tuser,

    /*
     * AXI Stream output
     */
    output wire [DATA_WIDTH-1:0]  m_axis_tdata,
    output wire [KEEP_WIDTH-1:0]  m_axis_tkeep,
    output wire                   m_axis_tvalid,
    input  wire                   m_axis_tready,
    output wire                   m_axis_tlast,
    output wire [ID_WIDTH-1:0]    m_axis_tid,
    output wire [DEST_WIDTH-1:0]  m_axis_tdest,
    output wire [USER_WIDTH-1:0]  m_axis_tuser
);

// RTLRefine-owned stateless adapter: pack metadata into the leaf's data bus.
localparam WORD_WIDTH=DATA_WIDTH+KEEP_WIDTH+1+ID_WIDTH+DEST_WIDTH+USER_WIDTH;
wire [WORD_WIDTH-1:0] packed_in={USER_ENABLE?s_axis_tuser:{USER_WIDTH{1'b0}},
 DEST_ENABLE?s_axis_tdest:{DEST_WIDTH{1'b0}},ID_ENABLE?s_axis_tid:{ID_WIDTH{1'b0}},
 LAST_ENABLE?s_axis_tlast:1'b1,KEEP_ENABLE?s_axis_tkeep:{KEEP_WIDTH{1'b1}},s_axis_tdata};
wire [WORD_WIDTH-1:0] packed_out;
skidbuffer #(.DW(WORD_WIDTH),.OPT_LOWPOWER(LOWPOWER),.OPT_OUTREG(REG_TYPE>1),
 .OPT_PASSTHROUGH(REG_TYPE==0),.OPT_INITIAL(1)) leaf(
 .i_clk(clk),.i_reset(rst),.i_valid(s_axis_tvalid),.o_ready(s_axis_tready),
 .i_data(packed_in),.o_valid(m_axis_tvalid),.i_ready(m_axis_tready),.o_data(packed_out));
assign {m_axis_tuser,m_axis_tdest,m_axis_tid,m_axis_tlast,m_axis_tkeep,m_axis_tdata}=packed_out;
endmodule
`resetall
