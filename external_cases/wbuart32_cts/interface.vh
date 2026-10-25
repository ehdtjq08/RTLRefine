////////////////////////////////////////////////////////////////////////////////
//
// Filename: 	txuart.v
//
// Project:	wbuart32, a full featured UART with simulator
//
// Purpose:	Transmit outputs over a single UART line.
//
//	To interface with this module, connect it to your system clock,
//	pass it the 32 bit setup register (defined below) and the byte
//	of data you wish to transmit.  Strobe the i_wr line high for one
//	clock cycle, and your data will be off.  Wait until the 'o_busy'
//	line is low before strobing the i_wr line again--this implementation
//	has NO BUFFER, so strobing i_wr while the core is busy will just
//	cause your data to be lost.  The output will be placed on the o_txuart
//	output line.  If you wish to set/send a break condition, assert the
//	i_break line otherwise leave it low.
//
//	There is a synchronous reset line, logic high.
//
//	Now for the setup register.  The register is 32 bits, so that this
//	UART may be set up over a 32-bit bus.
//
//	i_setup[30]	Set this to zero to use hardware flow control, and to
//		one to ignore hardware flow control.  Only works if the hardware
//		flow control has been properly wired.
//
//		If you don't want hardware flow control, fix the i_rts bit to
//		1'b1, and let the synthesys tools optimize out the logic.
//
//	i_setup[29:28]	Indicates the number of data bits per word.  This will
//		either be 2'b00 for an 8-bit word, 2'b01 for a 7-bit word, 2'b10
//		for a six bit word, or 2'b11 for a five bit word.
//
//	i_setup[27]	Indicates whether or not to use one or two stop bits.
//		Set this to one to expect two stop bits, zero for one.
//
//	i_setup[26]	Indicates whether or not a parity bit exists.  Set this
//		to 1'b1 to include parity.
//
//	i_setup[25]	Indicates whether or not the parity bit is fixed.  Set
//		to 1'b1 to include a fixed bit of parity, 1'b0 to allow the
//		parity to be set based upon data.  (Both assume the parity
//		enable value is set.)
//
//	i_setup[24]	This bit is ignored if parity is not used.  Otherwise,
//		in the case of a fixed parity bit, this bit indicates whether
//		mark (1'b1) or space (1'b0) parity is used.  Likewise if the
//		parity is not fixed, a 1'b1 selects even parity, and 1'b0
//		selects odd.
//
//	i_setup[23:0]	Indicates the speed of the UART in terms of clocks.
//		So, for example, if you have a 200 MHz clock and wish to
//		run your UART at 9600 baud, you would take 200 MHz and divide
//		by 9600 to set this value to 24'd20834.  Likewise if you wished
//		to run this serial port at 115200 baud from a 200 MHz clock,
//		you would set the value to 24'd1736
//
//	Thus, to set the UART for the common setting of an 8-bit word, 
//	one stop bit, no parity, and 115200 baud over a 200 MHz clock, you
//	would want to set the setup value to:
//
//	32'h0006c8		// For 115,200 baud, 8 bit, no parity
//	32'h005161		// For 9600 baud, 8 bit, no parity
//	
//
// Creator:	Dan Gisselquist, Ph.D.
//		Gisselquist Technology, LLC
//
////////////////////////////////////////////////////////////////////////////////
//
// Copyright (C) 2015-2019, Gisselquist Technology, LLC
//
// This program is free software (firmware): you can redistribute it and/or
// modify it under the terms of  the GNU General Public License as published
// by the Free Software Foundation, either version 3 of the License, or (at
// your option) any later version.
//
// This program is distributed in the hope that it will be useful, but WITHOUT
// ANY WARRANTY; without even the implied warranty of MERCHANTIBILITY or
// FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
// for more details.
//
// You should have received a copy of the GNU General Public License along
// with this program.  (It's in the $(ROOT)/doc directory.  Run make with no
// target there if the PDF file isn't present.)  If not, see
// <http://www.gnu.org/licenses/> for a copy.
//
// License:	GPL, v3, as defined and found on www.gnu.org,
//		http://www.gnu.org/licenses/gpl.html
//
//
////////////////////////////////////////////////////////////////////////////////
//
//
`default_nettype	none
//
//
module txuart(i_clk, i_reset, i_setup, i_break, i_wr, i_data,
		i_cts_n, o_uart_tx, o_busy);
	parameter	[30:0]	INITIAL_SETUP = 31'd868;
	//
	localparam 	[3:0]	TXU_BIT_ZERO  = 4'h0;
	localparam 	[3:0]	TXU_BIT_ONE   = 4'h1;
	localparam 	[3:0]	TXU_BIT_TWO   = 4'h2;
	localparam 	[3:0]	TXU_BIT_THREE = 4'h3;
	localparam 	[3:0]	TXU_BIT_FOUR  = 4'h4;
	localparam 	[3:0]	TXU_BIT_FIVE  = 4'h5;
	localparam 	[3:0]	TXU_BIT_SIX   = 4'h6;
	localparam 	[3:0]	TXU_BIT_SEVEN = 4'h7;
	localparam 	[3:0]	TXU_PARITY    = 4'h8;
	localparam 	[3:0]	TXU_STOP      = 4'h9;
	localparam 	[3:0]	TXU_SECOND_STOP = 4'ha;
	//
	localparam 	[3:0]	TXU_BREAK     = 4'he;
	localparam 	[3:0]	TXU_IDLE      = 4'hf;
	//
	//
	input	wire		i_clk, i_reset;
	input	wire	[30:0]	i_setup;
	input	wire		i_break;
	input	wire		i_wr;
	input	wire	[7:0]	i_data;
	// Hardware flow control Ready-To-Send bit.  Set this to one to use
	// the core without flow control.  (A more appropriate name would be
	// the Ready-To-Receive bit ...)
	input	wire		i_cts_n;
	// And the UART input line itself
	output	reg		o_uart_tx;
	// A line to tell others when we are ready to accept data.  If
	// (i_wr)&&(!o_busy) is ever true, then the core has accepted a byte
	// for transmission.
	output	wire		o_busy;

