////////////////////////////////////////////////////////////////////////////////
//
// Filename:	rtl/skidbuffer.v
// {{{
// Project:	WB2AXIPSP: bus bridges and other odds and ends
//
// Purpose:	A basic SKID buffer.
// {{{
//	Skid buffers are required for high throughput AXI code, since the AXI
//	specification requires that all outputs be registered.  This means
//	that, if there are any stall conditions calculated, it will take a clock
//	cycle before the stall can be propagated up stream.  This means that
//	the data will need to be buffered for a cycle until the stall signal
//	can make it to the output.
//
//	Handling that buffer is the purpose of this core.
//
//	On one end of this core, you have the i_valid and i_data inputs to
//	connect to your bus interface.  There's also a registered o_ready
//	signal to signal stalls for the bus interface.
//
//	The other end of the core has the same basic interface, but it isn't
//	registered.  This allows you to interact with the bus interfaces
//	as though they were combinatorial logic, by interacting with this half
//	of the core.
//
//	If at any time the incoming !stall signal, i_ready, signals a stall,
//	the incoming data is placed into a buffer.  Internally, that buffer
//	is held in r_data with the r_valid flag used to indicate that valid
//	data is within it.
// }}}
// Parameters:
// {{{
//	DW or data width
//		In order to make this core generic, the width of the data in the
//		skid buffer is parameterized
//
//	OPT_LOWPOWER
//		Forces both o_data and r_data to zero if the respective *VALID
//		signal is also low.  While this costs extra logic, it can also
//		be used to guarantee that any unused values aren't toggling and
//		therefore unnecessarily using power.
//
//		This excess toggling can be particularly problematic if the
//		bus signals have a high fanout rate, or a long signal path
//		across an FPGA.
//
//	OPT_OUTREG
//		Causes the outputs to be registered
//
//	OPT_PASSTHROUGH
//		Turns the skid buffer into a passthrough.  Used for formal
//		verification only.
// }}}
// Creator:	Dan Gisselquist, Ph.D.
//		Gisselquist Technology, LLC
//
////////////////////////////////////////////////////////////////////////////////
// }}}
// Copyright (C) 2019-2025, Gisselquist Technology, LLC
// {{{
// This file is part of the WB2AXIP project.
//
// The WB2AXIP project contains free software and gateware, licensed under the
// Apache License, Version 2.0 (the "License").  You may not use this project,
// or this file, except in compliance with the License.  You may obtain a copy
// of the License at
// }}}
//	http://www.apache.org/licenses/LICENSE-2.0
// {{{
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
// WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
// License for the specific language governing permissions and limitations
// under the License.
//
////////////////////////////////////////////////////////////////////////////////
//
`default_nettype none
// }}}
module skidbuffer #(
		// {{{
		parameter	[0:0]	OPT_LOWPOWER = 0,
		parameter	[0:0]	OPT_OUTREG = 1,
		//
		parameter	[0:0]	OPT_PASSTHROUGH = 0,
		parameter		DW = 8,
		parameter	[0:0]	OPT_INITIAL = 1'b1
		// }}}
	) (
		// {{{
		input	wire			i_clk, i_reset,
		input	wire			i_valid,
		output	wire			o_ready,
		input	wire	[DW-1:0]	i_data,
		output	wire			o_valid,
		input	wire			i_ready,
		output	reg	[DW-1:0]	o_data
		// }}}
	);

	wire	[DW-1:0]	w_data;

	generate if (OPT_PASSTHROUGH)
	begin : PASSTHROUGH
		// {{{
		assign	{ o_valid, o_ready } = { i_valid, i_ready };

		always @(*)
		if (!i_valid && OPT_LOWPOWER)
			o_data = 0;
		else
			o_data = i_data;

		assign	w_data = 0;

		// Keep Verilator happy
		// Verilator lint_off UNUSED
		// {{{
		wire	unused_passthrough;
		assign	unused_passthrough = &{ 1'b0, i_clk, i_reset };
		// }}}
		// Verilator lint_on  UNUSED
		// }}}
	end else begin : LOGIC
		// We'll start with skid buffer itself
		// {{{
		reg			r_valid;
		reg	[DW-1:0]	r_data;

		// r_valid
		// {{{
		initial if (OPT_INITIAL) r_valid = 0;
		always @(posedge i_clk)
		if (i_reset)
			r_valid <= 0;
		else if ((i_valid && o_ready) && (o_valid && !i_ready))
			// We have incoming data, but the output is stalled
			r_valid <= 1;
		else if (i_ready)
			r_valid <= 0;
		// }}}

		// r_data
		// {{{
		initial if (OPT_INITIAL) r_data = 0;
		always @(posedge i_clk)
		if (OPT_LOWPOWER && i_reset)
			r_data <= 0;
		else if (OPT_LOWPOWER && (!o_valid || i_ready))
			r_data <= 0;
		else if ((!OPT_LOWPOWER || !OPT_OUTREG || i_valid) && o_ready)
			r_data <= i_data;

		assign	w_data = r_data;
		// }}}

		// o_ready
		// {{{
		assign o_ready = !r_valid;
		// }}}

		//
		// And then move on to the output port
		//
		if (!OPT_OUTREG)
		begin : NET_OUTPUT
			// Outputs are combinatorially determined from inputs
			// {{{
			// o_valid
			// {{{
			assign	o_valid = !i_reset && (i_valid || r_valid);
			// }}}

			// o_data
			// {{{
			always @(*)
			if (r_valid)
				o_data = r_data;
			else if (!OPT_LOWPOWER || i_valid)
				o_data = i_data;
			else
				o_data = 0;
			// }}}
			// }}}
		end else begin : REG_OUTPUT
			// Register our outputs
			// {{{
			// o_valid
			// {{{
			reg	ro_valid;

			initial if (OPT_INITIAL) ro_valid = 0;
			always @(posedge i_clk)
			if (i_reset)
				ro_valid <= 0;
			else if (!o_valid || i_ready)
				ro_valid <= (i_valid || r_valid);

			assign	o_valid = ro_valid;
			// }}}

			// o_data
			// {{{
			initial if (OPT_INITIAL) o_data = 0;
			always @(posedge i_clk)
			if (OPT_LOWPOWER && i_reset)
				o_data <= 0;
			else if (!o_valid || i_ready)
			begin

				if (r_valid)
					o_data <= r_data;
				else if (!OPT_LOWPOWER || i_valid)
					o_data <= i_data;
				else
					o_data <= 0;
			end
			// }}}

			// }}}
		end
		// }}}
	end endgenerate

	// Keep Verilator happy
	// {{{
	// verilator coverage_off
	// Verilator lint_off UNUSED
	wire	unused;
	assign	unused = &{ 1'b0, w_data };
	// Verilator lint_on  UNUSED
	// verilator coverage_on
	// }}}
////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////
//
// Formal properties
// {{{
////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////
































































































































































































































































// }}}
endmodule
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
