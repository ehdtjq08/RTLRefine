`ifdef	FORMAL
	reg		fsv_parity;
	reg	[30:0]	fsv_setup;
	reg	[7:0]	fsv_data;
	reg		f_past_valid;

	initial	f_past_valid = 1'b0;
	always @(posedge  i_clk)
		f_past_valid <= 1'b1;

	always @(posedge i_clk)
	if ((i_wr)&&(!o_busy))
		fsv_data <= i_data;

	initial	fsv_setup = INITIAL_SETUP;
	always @(posedge i_clk)
	if (!o_busy)
		fsv_setup <= i_setup;

	always @(*)
		assert(r_setup == fsv_setup);


	always @(posedge i_clk)
		assert(zero_baud_counter == (baud_counter == 0));

	always @(*)
	if (!o_busy)
		assert(zero_baud_counter);

	/*
	*
	* Will only pass if !i_break && !i_reset, otherwise the setup can
	* change in the middle of this operation
	*
	always @(posedge i_clk)
	if ((f_past_valid)&&(!$past(i_reset))&&(!$past(i_break))
			&&(($past(o_busy))||($past(i_wr))))
		assert(baud_counter <= { fsv_setup[23:0], 4'h0 });
	*/

	// A single baud interval
	always @(posedge i_clk)
	if ((f_past_valid)&&(!$past(zero_baud_counter))
		&&(!$past(i_reset))&&(!$past(i_break)))
	begin
		assert($stable(o_uart_tx));
		assert($stable(state));
		assert($stable(lcl_data));
		if ((state != TXU_IDLE)&&(state != TXU_BREAK))
			assert($stable(calc_parity));
		assert(baud_counter == $past(baud_counter)-1'b1);
	end

	//
	// Our various sequence data declarations
	reg	[5:0]	f_five_seq;
	reg	[6:0]	f_six_seq;
	reg	[7:0]	f_seven_seq;
	reg	[8:0]	f_eight_seq;
	reg	[2:0]	f_stop_seq;	// parity bit, stop bit, double stop bit


	//
	// One byte transmitted
	//
	// DATA = the byte that is sent
	// CKS  = the number of clocks per bit
	//
	////////////////////////////////////////////////////////////////////////
	//
	// Five bit data
	//
	////////////////////////////////////////////////////////////////////////

	initial	f_five_seq = 0;
	always @(posedge i_clk)
	if ((i_reset)||(i_break))
		f_five_seq = 0;
	else if ((state == TXU_IDLE)&&(i_wr)&&(!o_busy)
			&&(i_data_bits == 2'b11)) // five data bits
		f_five_seq <= 1;
	else if (zero_baud_counter)
		f_five_seq <= f_five_seq << 1;

	always @(*)
	if (|f_five_seq)
	begin
		assert(fsv_setup[29:28] == data_bits);
		assert(data_bits == 2'b11);
		assert(baud_counter < fsv_setup[23:0]);

		assert(1'b0 == |f_six_seq);
		assert(1'b0 == |f_seven_seq);
		assert(1'b0 == |f_eight_seq);
		assert(r_busy);
		assert(state > 4'h2);
	end

	always @(*)
	case(f_five_seq)
	6'h00: begin assert(1); end
	6'h01: begin
		assert(state == 4'h3);
		assert(o_uart_tx == 1'b0);
		assert(lcl_data[4:0] == fsv_data[4:0]);
		if (!fixd_parity)
			assert(calc_parity == parity_odd);
	end
	6'h02: begin
		assert(state == 4'h4);
		assert(o_uart_tx == fsv_data[0]);
		assert(lcl_data[3:0] == fsv_data[4:1]);
		if (!fixd_parity)
			assert(calc_parity == fsv_data[0] ^ parity_odd);
	end
	6'h04: begin
		assert(state == 4'h5);
		assert(o_uart_tx == fsv_data[1]);
		assert(lcl_data[2:0] == fsv_data[4:2]);
		if (!fixd_parity)
			assert(calc_parity == (^fsv_data[1:0]) ^ parity_odd);
	end
	6'h08: begin
		assert(state == 4'h6);
		assert(o_uart_tx == fsv_data[2]);
		assert(lcl_data[1:0] == fsv_data[4:3]);
		if (!fixd_parity)
			assert(calc_parity == (^fsv_data[2:0]) ^ parity_odd);
	end
	6'h10: begin
		assert(state == 4'h7);
		assert(o_uart_tx == fsv_data[3]);
		assert(lcl_data[0] == fsv_data[4]);
		if (!fixd_parity)
			assert(calc_parity == (^fsv_data[3:0]) ^ parity_odd);
	end
	6'h20: begin
		if (use_parity)
			assert(state == 4'h8);
		else
			assert(state == 4'h9);
		assert(o_uart_tx == fsv_data[4]);
		if (!fixd_parity)
			assert(calc_parity == (^fsv_data[4:0]) ^ parity_odd);
	end
	default: begin assert(0); end
	endcase

	////////////////////////////////////////////////////////////////////////
	//
	// Six bit data
	//
	////////////////////////////////////////////////////////////////////////

	initial	f_six_seq = 0;
	always @(posedge i_clk)
	if ((i_reset)||(i_break))
		f_six_seq = 0;
	else if ((state == TXU_IDLE)&&(i_wr)&&(!o_busy)
			&&(i_data_bits == 2'b10)) // six data bits
		f_six_seq <= 1;
	else if (zero_baud_counter)
		f_six_seq <= f_six_seq << 1;

	always @(*)
	if (|f_six_seq)
	begin
		assert(fsv_setup[29:28] == 2'b10);
		assert(fsv_setup[29:28] == data_bits);
		assert(baud_counter < fsv_setup[23:0]);

		assert(1'b0 == |f_five_seq);
		assert(1'b0 == |f_seven_seq);
		assert(1'b0 == |f_eight_seq);
		assert(r_busy);
		assert(state > 4'h1);
	end

	always @(*)
	case(f_six_seq)
	7'h00: begin assert(1); end
	7'h01: begin
		assert(state == 4'h2);
		assert(o_uart_tx == 1'b0);
		assert(lcl_data[5:0] == fsv_data[5:0]);
		if (!fixd_parity)
			assert(calc_parity == parity_odd);
	end
	7'h02: begin
		assert(state == 4'h3);
		assert(o_uart_tx == fsv_data[0]);
		assert(lcl_data[4:0] == fsv_data[5:1]);
		if (!fixd_parity)
			assert(calc_parity == fsv_data[0] ^ parity_odd);
	end
	7'h04: begin
		assert(state == 4'h4);
		assert(o_uart_tx == fsv_data[1]);
		assert(lcl_data[3:0] == fsv_data[5:2]);
		if (!fixd_parity)
			assert(calc_parity == (^fsv_data[1:0]) ^ parity_odd);
	end
	7'h08: begin
		assert(state == 4'h5);
		assert(o_uart_tx == fsv_data[2]);
		assert(lcl_data[2:0] == fsv_data[5:3]);
		if (!fixd_parity)
			assert(calc_parity == (^fsv_data[2:0]) ^ parity_odd);
	end
	7'h10: begin
		assert(state == 4'h6);
		assert(o_uart_tx == fsv_data[3]);
		assert(lcl_data[1:0] == fsv_data[5:4]);
		if (!fixd_parity)
			assert(calc_parity == (^fsv_data[3:0]) ^ parity_odd);
	end
	7'h20: begin
		assert(state == 4'h7);
		assert(lcl_data[0] == fsv_data[5]);
		assert(o_uart_tx == fsv_data[4]);
		if (!fixd_parity)
			assert(calc_parity == ((^fsv_data[4:0]) ^ parity_odd));
	end
	7'h40: begin
		if (use_parity)
			assert(state == 4'h8);
		else
			assert(state == 4'h9);
		assert(o_uart_tx == fsv_data[5]);
		if (!fixd_parity)
			assert(calc_parity == ((^fsv_data[5:0]) ^ parity_odd));
	end
	default: begin if (f_past_valid) assert(0); end
	endcase

	////////////////////////////////////////////////////////////////////////
	//
	// Seven bit data
	//
	////////////////////////////////////////////////////////////////////////
	initial	f_seven_seq = 0;
	always @(posedge i_clk)
	if ((i_reset)||(i_break))
		f_seven_seq = 0;
	else if ((state == TXU_IDLE)&&(i_wr)&&(!o_busy)
			&&(i_data_bits == 2'b01)) // seven data bits
		f_seven_seq <= 1;
	else if (zero_baud_counter)
		f_seven_seq <= f_seven_seq << 1;

	always @(*)
	if (|f_seven_seq)
	begin
		assert(fsv_setup[29:28] == 2'b01);
		assert(fsv_setup[29:28] == data_bits);
		assert(baud_counter < fsv_setup[23:0]);

		assert(1'b0 == |f_five_seq);
		assert(1'b0 == |f_six_seq);
		assert(1'b0 == |f_eight_seq);
		assert(r_busy);
		assert(state != 4'h0);
	end

	always @(*)
	case(f_seven_seq)
	8'h00: begin assert(1); end
	8'h01: begin
		assert(state == 4'h1);
		assert(o_uart_tx == 1'b0);
		assert(lcl_data[6:0] == fsv_data[6:0]);
		if (!fixd_parity)
			assert(calc_parity == parity_odd);
	end
	8'h02: begin
		assert(state == 4'h2);
		assert(o_uart_tx == fsv_data[0]);
		assert(lcl_data[5:0] == fsv_data[6:1]);
		if (!fixd_parity)
			assert(calc_parity == fsv_data[0] ^ parity_odd);
	end
	8'h04: begin
		assert(state == 4'h3);
		assert(o_uart_tx == fsv_data[1]);
		assert(lcl_data[4:0] == fsv_data[6:2]);
		if (!fixd_parity)
			assert(calc_parity == (^fsv_data[1:0]) ^ parity_odd);
	end
	8'h08: begin
		assert(state == 4'h4);
		assert(o_uart_tx == fsv_data[2]);
		assert(lcl_data[3:0] == fsv_data[6:3]);
		if (!fixd_parity)
			assert(calc_parity == (^fsv_data[2:0]) ^ parity_odd);
	end
	8'h10: begin
		assert(state == 4'h5);
		assert(o_uart_tx == fsv_data[3]);
		assert(lcl_data[2:0] == fsv_data[6:4]);
		if (!fixd_parity)
			assert(calc_parity == (^fsv_data[3:0]) ^ parity_odd);
	end
	8'h20: begin
		assert(state == 4'h6);
		assert(o_uart_tx == fsv_data[4]);
		assert(lcl_data[1:0] == fsv_data[6:5]);
		if (!fixd_parity)
			assert(calc_parity == ((^fsv_data[4:0]) ^ parity_odd));
	end
	8'h40: begin
		assert(state == 4'h7);
		assert(lcl_data[0] == fsv_data[6]);
		assert(o_uart_tx == fsv_data[5]);
		if (!fixd_parity)
			assert(calc_parity == ((^fsv_data[5:0]) ^ parity_odd));
	end
	8'h80: begin
		if (use_parity)
			assert(state == 4'h8);
		else
			assert(state == 4'h9);
		assert(o_uart_tx == fsv_data[6]);
		if (!fixd_parity)
			assert(calc_parity == ((^fsv_data[6:0]) ^ parity_odd));
	end
	default: begin if (f_past_valid) assert(0); end
	endcase


	////////////////////////////////////////////////////////////////////////
	//
	// Eight bit data
	//
	////////////////////////////////////////////////////////////////////////
	initial	f_eight_seq = 0;
	always @(posedge i_clk)
	if ((i_reset)||(i_break))
		f_eight_seq = 0;
	else if ((state == TXU_IDLE)&&(i_wr)&&(!o_busy)
			&&(i_data_bits == 2'b00)) // Eight data bits
		f_eight_seq <= 1;
	else if (zero_baud_counter)
		f_eight_seq <= f_eight_seq << 1;

	always @(*)
	if (|f_eight_seq)
	begin
		assert(fsv_setup[29:28] == 2'b00);
		assert(fsv_setup[29:28] == data_bits);
		assert(baud_counter < { 6'h0, fsv_setup[23:0]});

		assert(1'b0 == |f_five_seq);
		assert(1'b0 == |f_six_seq);
		assert(1'b0 == |f_seven_seq);
		assert(r_busy);
	end

	always @(*)
	case(f_eight_seq)
	9'h000: begin assert(1); end
	9'h001: begin
		assert(state == 4'h0);
		assert(o_uart_tx == 1'b0);
		assert(lcl_data[7:0] == fsv_data[7:0]);
		if (!fixd_parity)
			assert(calc_parity == parity_odd);
	end
	9'h002: begin
		assert(state == 4'h1);
		assert(o_uart_tx == fsv_data[0]);
		assert(lcl_data[6:0] == fsv_data[7:1]);
		if (!fixd_parity)
			assert(calc_parity == fsv_data[0] ^ parity_odd);
	end
	9'h004: begin
		assert(state == 4'h2);
		assert(o_uart_tx == fsv_data[1]);
		assert(lcl_data[5:0] == fsv_data[7:2]);
		if (!fixd_parity)
			assert(calc_parity == (^fsv_data[1:0]) ^ parity_odd);
	end
	9'h008: begin
		assert(state == 4'h3);
		assert(o_uart_tx == fsv_data[2]);
		assert(lcl_data[4:0] == fsv_data[7:3]);
		if (!fixd_parity)
			assert(calc_parity == (^fsv_data[2:0]) ^ parity_odd);
	end
	9'h010: begin
		assert(state == 4'h4);
		assert(o_uart_tx == fsv_data[3]);
		assert(lcl_data[3:0] == fsv_data[7:4]);
		if (!fixd_parity)
			assert(calc_parity == (^fsv_data[3:0]) ^ parity_odd);
	end
	9'h020: begin
		assert(state == 4'h5);
		assert(o_uart_tx == fsv_data[4]);
		assert(lcl_data[2:0] == fsv_data[7:5]);
		if (!fixd_parity)
			assert(calc_parity == (^fsv_data[4:0]) ^ parity_odd);
	end
	9'h040: begin
		assert(state == 4'h6);
		assert(o_uart_tx == fsv_data[5]);
		assert(lcl_data[1:0] == fsv_data[7:6]);
		if (!fixd_parity)
			assert(calc_parity == (^fsv_data[5:0]) ^ parity_odd);
	end
	9'h080: begin
		assert(state == 4'h7);
		assert(o_uart_tx == fsv_data[6]);
		assert(lcl_data[0] == fsv_data[7]);
		if (!fixd_parity)
			assert(calc_parity == ((^fsv_data[6:0]) ^ parity_odd));
	end
	9'h100: begin
		if (use_parity)
			assert(state == 4'h8);
		else
			assert(state == 4'h9);
		assert(o_uart_tx == fsv_data[7]);
		if (!fixd_parity)
			assert(calc_parity == ((^fsv_data[7:0]) ^ parity_odd));
	end
	default: begin if (f_past_valid) assert(0); end
	endcase

	////////////////////////////////////////////////////////////////////////
	//
	// Combined properties for all of the data sequences
	//
	////////////////////////////////////////////////////////////////////////
	always @(posedge i_clk)
	if (((|f_five_seq[5:0]) || (|f_six_seq[6:0]) || (|f_seven_seq[7:0])
			|| (|f_eight_seq[8:0]))
		&& ($past(zero_baud_counter)))
		assert(baud_counter == { 4'h0, fsv_setup[23:0] }-1);


	////////////////////////////////////////////////////////////////////////
	//
	// The stop sequence
	//
	// This consists of any parity bit, as well as one or two stop bits
	////////////////////////////////////////////////////////////////////////
	initial	f_stop_seq = 1'b0;
	always @(posedge i_clk)
	if ((i_reset)||(i_break))
		f_stop_seq <= 0;
	else if (zero_baud_counter)
	begin
		f_stop_seq <= 0;
		if (f_stop_seq[0]) // Coming from a parity bit
		begin
			if (dblstop)
				f_stop_seq[1] <= 1'b1;
			else
				f_stop_seq[2] <= 1'b1;
		end

		if (f_stop_seq[1])
			f_stop_seq[2] <= 1'b1;

		if (f_eight_seq[8] | f_seven_seq[7] | f_six_seq[6]
			| f_five_seq[5])
		begin
			if (use_parity)
				f_stop_seq[0] <= 1'b1;
			else if (dblstop)
				f_stop_seq[1] <= 1'b1;
			else
				f_stop_seq[2] <= 1'b1;
		end
	end

	always @(*)
	if (|f_stop_seq)
	begin
		assert(1'b0 == |f_five_seq[4:0]);
		assert(1'b0 == |f_six_seq[5:0]);
		assert(1'b0 == |f_seven_seq[6:0]);
		assert(1'b0 == |f_eight_seq[7:0]);

		assert(r_busy);
	end

	always @(*)
	if (f_stop_seq[0])
	begin
		// 9 if dblstop and use_parity
		if (dblstop)
			assert(state == TXU_STOP);
		else
			assert(state == TXU_STOP);
		assert(use_parity);
		assert(o_uart_tx == fsv_parity);
	end
		
	always @(*)
	if (f_stop_seq[1])
	begin
		// if (!use_parity)
		assert(state == TXU_SECOND_STOP);
		assert(dblstop);
		assert(o_uart_tx);
	end

	always @(*)
	if (f_stop_seq[2])
	begin
		assert(state == 4'hf);
		assert(o_uart_tx);
		assert(baud_counter < fsv_setup[23:0]-1'b1);
	end
		

	always @(*)
	if (fsv_setup[25])
		fsv_parity <= fsv_setup[24];
	else
		case(fsv_setup[29:28])
		2'b00: fsv_parity = (^fsv_data[7:0]) ^ fsv_setup[24];
		2'b01: fsv_parity = (^fsv_data[6:0]) ^ fsv_setup[24];
		2'b10: fsv_parity = (^fsv_data[5:0]) ^ fsv_setup[24];
		2'b11: fsv_parity = (^fsv_data[4:0]) ^ fsv_setup[24];
		endcase

	//////////////////////////////////////////////////////////////////////
	//
	// The break sequence
	//
	//////////////////////////////////////////////////////////////////////
	reg	[1:0]	f_break_seq;
	initial	f_break_seq = 2'b00;
	always @(posedge i_clk)
	if (i_reset)
		f_break_seq <= 2'b00;
	else if (i_break)
		f_break_seq <= 2'b01;
	else if (!zero_baud_counter)
		f_break_seq <= { |f_break_seq, 1'b0 };
	else
		f_break_seq <= 0;

	always @(posedge i_clk)
	if (f_break_seq[0])
		assert(baud_counter == { $past(fsv_setup[23:0]), 4'h0 });
	always @(posedge i_clk)
	if ((f_past_valid)&&($past(f_break_seq[1]))&&(state != TXU_BREAK))
	begin
		assert(state == TXU_IDLE);
		assert(o_uart_tx == 1'b1);
	end

	always @(*)
	if (|f_break_seq)
	begin
		assert(state == TXU_BREAK);
		assert(r_busy);
		assert(o_uart_tx == 1'b0);
	end

	//////////////////////////////////////////////////////////////////////
	//
	// Properties for use during induction if we are made a submodule of
	// the rxuart
	//
	//////////////////////////////////////////////////////////////////////

	// Need enough bits for reset (24+4) plus enough bits for all of the
	// various characters, 24+4, so 24+5 is a minimum of this counter
	//
`ifndef	TXUART
	reg	[28:0]		f_counter;
	initial	f_counter = 0;
	always @(posedge i_clk)
	if (!o_busy)
		f_counter <= 1'b0;
	else
		f_counter <= f_counter + 1'b1;

	always @(*)
	if (f_five_seq[0]|f_six_seq[0]|f_seven_seq[0]|f_eight_seq[0])
		assert(f_counter == (fsv_setup[23:0] - baud_counter - 1));
	else if (f_five_seq[1]|f_six_seq[1]|f_seven_seq[1]|f_eight_seq[1])
		assert(f_counter == ({4'h0, fsv_setup[23:0], 1'b0} - baud_counter - 1));
	else if (f_five_seq[2]|f_six_seq[2]|f_seven_seq[2]|f_eight_seq[2])
		assert(f_counter == ({4'h0, fsv_setup[23:0], 1'b0}
				+{5'h0, fsv_setup[23:0]}
				- baud_counter - 1));
	else if (f_five_seq[3]|f_six_seq[3]|f_seven_seq[3]|f_eight_seq[3])
		assert(f_counter == ({3'h0, fsv_setup[23:0], 2'b0}
				- baud_counter - 1));
	else if (f_five_seq[4]|f_six_seq[4]|f_seven_seq[4]|f_eight_seq[4])
		assert(f_counter == ({3'h0, fsv_setup[23:0], 2'b0}
				+{5'h0, fsv_setup[23:0]}
				- baud_counter - 1));
	else if (f_five_seq[5]|f_six_seq[5]|f_seven_seq[5]|f_eight_seq[5])
		assert(f_counter == ({3'h0, fsv_setup[23:0], 2'b0}
				+{4'h0, fsv_setup[23:0], 1'b0}
				- baud_counter - 1));
	else if (f_six_seq[6]|f_seven_seq[6]|f_eight_seq[6])
		assert(f_counter == ({3'h0, fsv_setup[23:0], 2'b0}
				+{5'h0, fsv_setup[23:0]}
				+{4'h0, fsv_setup[23:0], 1'b0}
				- baud_counter - 1));
	else if (f_seven_seq[7]|f_eight_seq[7])
		assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}	// 8
				- baud_counter - 1));
	else if (f_eight_seq[8])
		assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}	// 9
				+{5'h0, fsv_setup[23:0]}
				- baud_counter - 1));
	else if (f_stop_seq[0] || (!use_parity && f_stop_seq[1]))
	begin
		// Parity bit, or first of two stop bits
		case(data_bits)
		2'b00: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				+{4'h0, fsv_setup[23:0], 1'b0} // 10
				- baud_counter - 1));
		2'b01: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				+{5'h0, fsv_setup[23:0]} // 9
				- baud_counter - 1));
		2'b10: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				- baud_counter - 1)); // 8
		2'b11: assert(f_counter == ({3'h0, fsv_setup[23:0], 2'b0}
				+{5'h0, fsv_setup[23:0]}	// 7
				+{4'h0, fsv_setup[23:0], 1'b0}
				- baud_counter - 1));
		endcase
	end else if (!use_parity && !dblstop  && f_stop_seq[2])
	begin
		// No parity, single stop bit
		// Different from the one above, since the last counter is has
		// one fewer items within it
		case(data_bits)
		2'b00: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				+{4'h0, fsv_setup[23:0], 1'b0} // 10
				- baud_counter - 2));
		2'b01: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				+{5'h0, fsv_setup[23:0]} // 9
				- baud_counter - 2));
		2'b10: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				- baud_counter - 2)); // 8
		2'b11: assert(f_counter == ({3'h0, fsv_setup[23:0], 2'b0}
				+{5'h0, fsv_setup[23:0]}	// 7
				+{4'h0, fsv_setup[23:0], 1'b0}
				- baud_counter - 2));
		endcase
	end else if (f_stop_seq[1])
	begin
		// Parity and the first of two stop bits
		assert(dblstop && use_parity);
		case(data_bits)
		2'b00: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				+{5'h0, fsv_setup[23:0]}	// 11
				+{4'h0, fsv_setup[23:0], 1'b0}
				- baud_counter - 1));
		2'b01: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				+{4'h0, fsv_setup[23:0], 1'b0} // 10
				- baud_counter - 1));
		2'b10: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				+{5'h0, fsv_setup[23:0]}	// 9
				- baud_counter - 1));
		2'b11: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				- baud_counter - 1));		// 8
		endcase
	end else if ((dblstop ^ use_parity) && f_stop_seq[2])
	begin
		// Parity and one stop bit
		// assert(!dblstop && use_parity);
		case(data_bits)
		2'b00: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				+{5'h0, fsv_setup[23:0]}	// 11
				+{4'h0, fsv_setup[23:0], 1'b0}
				- baud_counter - 2));
		2'b01: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				+{4'h0, fsv_setup[23:0], 1'b0} // 10
				- baud_counter - 2));
		2'b10: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				+{5'h0, fsv_setup[23:0]}	// 9
				- baud_counter - 2));
		2'b11: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				- baud_counter - 2));		// 8
		endcase
	end else if (f_stop_seq[2])
	begin
		assert(dblstop);
		assert(use_parity);
		// Parity and two stop bits
		case(data_bits)
		2'b00: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				+{3'h0, fsv_setup[23:0], 2'b00}	// 12
				- baud_counter - 2));
		2'b01: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				+{5'h0, fsv_setup[23:0]}	// 11
				+{4'h0, fsv_setup[23:0], 1'b0}
				- baud_counter - 2));
		2'b10: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				+{4'h0, fsv_setup[23:0], 1'b0} // 10
				- baud_counter - 2));
		2'b11: assert(f_counter == ({2'h0, fsv_setup[23:0], 3'b0}
				+{5'h0, fsv_setup[23:0]}	// 9
				- baud_counter - 2));
		endcase
	end
`endif

	//////////////////////////////////////////////////////////////////////
	//
	// Other properties, not necessarily associated with any sequences
	//
	//////////////////////////////////////////////////////////////////////
	always @(*)
		assert((state < 4'hb)||(state >= 4'he));
	//////////////////////////////////////////////////////////////////////
	//
	// Careless/limiting assumption section
	//
	//////////////////////////////////////////////////////////////////////
	always @(*)
		assume(i_setup[23:0] > 2);
	always @(*)
		assert(fsv_setup[23:0] > 2);

`endif	// FORMAL
endmodule

