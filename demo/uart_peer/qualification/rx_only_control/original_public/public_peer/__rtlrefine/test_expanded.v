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
 * AXI4-Stream UART
 */
module uart_tx #
(
    parameter DATA_WIDTH = 8
)
(
    input  wire                   clk,
    input  wire                   rst,

    /*
     * AXI input
     */
    input  wire [DATA_WIDTH-1:0]  input_axi_tdata,
    input  wire                   input_axi_tvalid,
    output wire                   input_axi_tready,

    /*
     * UART interface
     */
    output wire                   txd,

    /*
     * Status
     */
    output wire                   busy,

    /*
     * Configuration
     */
    input  wire [15:0]            prescale
);

reg input_axi_tready_reg = 0;

reg txd_reg = 1;

reg busy_reg = 0;

reg [DATA_WIDTH:0] data_reg = 0;
reg [18:0] prescale_reg = 0;
reg [3:0] bit_cnt = 0;

assign input_axi_tready = input_axi_tready_reg;
assign txd = txd_reg;

assign busy = busy_reg;

always @(posedge clk or posedge rst) begin
    if (rst) begin
        input_axi_tready_reg <= 0;
        txd_reg <= 1;
        prescale_reg <= 0;
        bit_cnt <= 0;
        busy_reg <= 0;
    end else begin
        if (prescale_reg > 0) begin
            input_axi_tready_reg <= 0;
            prescale_reg <= prescale_reg - 1;
        end else if (bit_cnt == 0) begin
            input_axi_tready_reg <= 1;
            busy_reg <= 0;

            if (input_axi_tvalid) begin
                input_axi_tready_reg <= ~input_axi_tready_reg;
                prescale_reg <= (prescale << 3)-1;
                bit_cnt <= DATA_WIDTH+1;
                data_reg <= {input_axi_tdata, 1'b1};
                txd_reg <= 0;
                busy_reg <= 1;
            end
        end else begin
            if (bit_cnt > 1) begin
                bit_cnt <= bit_cnt - 1;
                prescale_reg <= (prescale << 3)-1;
                {txd_reg, data_reg} <= {data_reg, 1'b0};
            end else if (bit_cnt == 1) begin
                bit_cnt <= bit_cnt - 1;
                prescale_reg <= (prescale << 3);
                txd_reg <= 1;
            end
        end
    end
end

endmodule
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
 * AXI4-Stream UART
 */
module uart_rx #
(
    parameter DATA_WIDTH = 8
)
(
    input  wire                   clk,
    input  wire                   rst,

    /*
     * AXI output
     */
    output wire [DATA_WIDTH-1:0]  output_axi_tdata,
    output wire                   output_axi_tvalid,
    input  wire                   output_axi_tready,

    /*
     * UART interface
     */
    input  wire                   rxd,

    /*
     * Status
     */
    output wire                   busy,
    output wire                   overrun_error,
    output wire                   frame_error,

    /*
     * Configuration
     */
    input  wire [15:0]            prescale

);

reg [DATA_WIDTH-1:0] output_axi_tdata_reg = 0;
reg output_axi_tvalid_reg = 0;

reg busy_reg = 0;
reg overrun_error_reg = 0;
reg frame_error_reg = 0;

reg [DATA_WIDTH-1:0] data_reg = 0;
reg [18:0] prescale_reg = 0;
reg [3:0] bit_cnt = 0;

assign output_axi_tdata = output_axi_tdata_reg;
assign output_axi_tvalid = output_axi_tvalid_reg;

assign busy = busy_reg;
assign overrun_error = overrun_error_reg;
assign frame_error = frame_error_reg;

always @(posedge clk or posedge rst) begin
    if (rst) begin
        output_axi_tdata_reg <= 0;
        output_axi_tvalid_reg <= 0;
        prescale_reg <= 0;
        bit_cnt <= 0;
        busy_reg <= 0;
        overrun_error_reg <= 0;
        frame_error_reg <= 0;
    end else begin
        overrun_error_reg <= 0;
        frame_error_reg <= 0;

        if (output_axi_tvalid & output_axi_tready) begin
            output_axi_tvalid_reg <= 0;
        end

        if (prescale_reg > 0) begin
            prescale_reg <= prescale_reg - 1;
        end else if (bit_cnt > 0) begin
            if (bit_cnt > DATA_WIDTH+1) begin
                if (~rxd) begin
                    bit_cnt <= bit_cnt - 1;
                    prescale_reg <= (prescale << 3)-1;
                end else begin
                    bit_cnt <= 0;
                    prescale_reg <= 0;
                end
            end else if (bit_cnt > 1) begin
                bit_cnt <= bit_cnt - 1;
                prescale_reg <= (prescale << 3)-1;
                data_reg <= {rxd, data_reg[DATA_WIDTH-1:1]};
            end else if (bit_cnt == 1) begin
                bit_cnt <= bit_cnt - 1;
                if (rxd) begin
                    output_axi_tdata_reg <= data_reg;
                    output_axi_tvalid_reg <= 1;
                    overrun_error_reg <= output_axi_tvalid_reg;
                end else begin
                    frame_error_reg <= 1;
                end
            end
        end else begin
            busy_reg <= 0;
            if (~rxd) begin
                prescale_reg <= (prescale << 2)-2;
                bit_cnt <= DATA_WIDTH+2;
                data_reg <= 0;
                busy_reg <= 1;
            end
        end
    end
end

endmodule
// RTLRefine stateless packaging adapter, MIT. Vendor leaf headers are retained.
module uart_pair #(parameter DATA_WIDTH=8)(
 input wire clk,rst,
 input wire [DATA_WIDTH-1:0] tx_data,
 input wire tx_valid,
 output wire tx_ready,txd,tx_busy,
 input wire rxd,
 output wire [DATA_WIDTH-1:0] rx_data,
 output wire rx_valid,
 input wire rx_ready,
 output wire rx_busy,overrun_error,frame_error,
 input wire [15:0] prescale
);
uart_tx #(.DATA_WIDTH(DATA_WIDTH)) tx(.clk(clk),.rst(rst),
 .input_axi_tdata(tx_data),.input_axi_tvalid(tx_valid),.input_axi_tready(tx_ready),
 .txd(txd),.busy(tx_busy),.prescale(prescale));
uart_rx #(.DATA_WIDTH(DATA_WIDTH)) rx(.clk(clk),.rst(rst),
 .output_axi_tdata(rx_data),.output_axi_tvalid(rx_valid),.output_axi_tready(rx_ready),
 .rxd(rxd),.busy(rx_busy),.overrun_error(overrun_error),.frame_error(frame_error),.prescale(prescale));
endmodule
`timescale 1ns/1ps




module tb_public;
parameter DATA_WIDTH=8;
parameter PRESCALE=2;
parameter WORDS=3;
parameter SEED=32'h3741a9b3;
parameter LOOPBACK_ONLY=0;
parameter STRESS=0;
localparam BAUD=PRESCALE*8;
localparam MASK=(1<<DATA_WIDTH)-1;
reg clk=0,rst=0,tx_valid=0,rx_ready=1,peer_line=1,loopback=0;
reg [DATA_WIDTH-1:0] tx_data=0;
wire tx_ready,txd,tx_busy,rx_valid,rx_busy,overrun_error,frame_error;
wire [DATA_WIDTH-1:0] rx_data;
wire rxd=loopback ? txd : peer_line;
uart_pair #(.DATA_WIDTH(DATA_WIDTH)) dut(.clk(clk),.rst(rst),.tx_data(tx_data),
 .tx_valid(tx_valid),.tx_ready(tx_ready),.txd(txd),.tx_busy(tx_busy),.rxd(rxd),
 .rx_data(rx_data),.rx_valid(rx_valid),.rx_ready(rx_ready),.rx_busy(rx_busy),
 .overrun_error(overrun_error),.frame_error(frame_error),.prescale(16'(PRESCALE)));
integer checks=0,cycles=0,rx_count=0,frame_errors=0,overrun_errors=0;
integer tx_bad=0,rx_bad=0,loopback_bad=0,control_bad=0;
integer n,k,limit,base_count,base_errors;
reg [DATA_WIDTH-1:0] received[0:4095];
reg [31:0] rng=SEED;
reg pre_ready=0;

function [31:0] random_next;
input [31:0] x;
reg [31:0] t;
begin t=x^(x<<13);t=t^(t>>17);random_next=t^(t<<5);end
endfunction

function [DATA_WIDTH-1:0] word_value;
input integer i;
begin
 case(i)
 0:word_value=1;
 1:word_value=1<<(DATA_WIDTH-1);
 2:word_value=8'h96;
 3:word_value=0;
 4:word_value=MASK;
 default:begin rng=random_next(rng);word_value=rng;end
 endcase
end
endfunction

task tick;
begin
 clk=0;#4;
 pre_ready=tx_ready;
 if(!rst && rx_valid && rx_ready) begin
  if(rx_count>=4096)$fatal(1,"HARNESS receive queue overflow");
  received[rx_count]=rx_data;rx_count=rx_count+1;
 end
 clk=1;#1;cycles=cycles+1;
 if(^ {tx_ready,txd,tx_busy,rx_valid,rx_busy,frame_error,overrun_error}===1'bx)
  $fatal(1,"UNKNOWN external UART control");
 checks=checks+1;
 if(rst) begin
  if(txd!==1 || tx_busy!==0 || rx_valid!==0 || rx_busy!==0)
   $fatal(1,"RESET UART outputs did not return idle");
  checks=checks+1;
 end
 if(!rst) begin
  if(frame_error)frame_errors=frame_errors+1;
  if(overrun_error)overrun_errors=overrun_errors+1;
 end
 clk=0;#5;
end
endtask

task reset_design;
begin
 tx_valid=0;peer_line=1;loopback=0;rx_ready=1;
 rst=1;tick();tick();rst=0;repeat(BAUD*2)tick();
end
endtask

task wait_tx_ready;
integer wait_cycles;
begin
 wait_cycles=0;
 while((tx_ready!==1 || tx_busy!==0) && wait_cycles<BAUD*(DATA_WIDTH+5))begin tick();wait_cycles=wait_cycles+1;end
 if(tx_ready!==1 || tx_busy!==0)$fatal(1,"TX_PROGRESS no input acceptance capacity");
 checks=checks+1;
end
endtask

task transmit_word;
input [DATA_WIDTH-1:0] value;
input integer independent;
integer age,bit_index,bit_errors;
reg expected;
reg [DATA_WIDTH-1:0] observed;
begin
 wait_tx_ready();tx_data=value;tx_valid=1;tick();
 if(!pre_ready)$fatal(1,"HARNESS offer was not accepted");
 tx_valid=0;checks=checks+1;
 if(txd!==0)$fatal(1,"TX_START missing start after accepted byte");
 observed=0;bit_errors=0;
 for(age=0;age<(DATA_WIDTH+2)*BAUD;age=age+1)begin
  if(age>0)tick();
  bit_index=age/BAUD;
  expected=bit_index==0 ? 0 : bit_index>DATA_WIDTH ? 1 : (value>>(bit_index-1))&1;
  if(independent && txd!==expected)bit_errors=bit_errors+1;
  if(independent)checks=checks+1;
  for(bit_index=0;bit_index<DATA_WIDTH;bit_index=bit_index+1)
   if(age==(bit_index+1)*BAUD+BAUD/2)observed[bit_index]=txd;
 end
 if(independent)begin
  $display("UART_TX_FRAME offered=%h observed_lsb=%h bit_errors=%0d",value,observed,bit_errors);
  if(bit_errors)tx_bad=tx_bad+1;
 end
 wait_tx_ready();repeat(BAUD*2)tick();
end
endtask

task drive_serial;
input [DATA_WIDTH-1:0] value;
input integer bad_stop;
integer bit_index;
begin
 peer_line=0;repeat(BAUD)tick();
 for(bit_index=0;bit_index<DATA_WIDTH;bit_index=bit_index+1)begin
  peer_line=value[bit_index];repeat(BAUD)tick();
 end
 peer_line=!bad_stop;repeat(BAUD)tick();
 peer_line=1;repeat(BAUD*2)tick();
end
endtask

task receive_word;
input [DATA_WIDTH-1:0] value;
integer prior_count;
begin
 prior_count=rx_count;rx_ready=1;drive_serial(value,0);
 if(rx_count!=prior_count+1)begin
  $display("UART_RX_COUNT expected=1 actual=%0d",rx_count-prior_count);rx_bad=rx_bad+1;
 end else begin
  $display("UART_RX_FRAME sent_lsb=%h decoded=%h",value,received[prior_count]);
  if(received[prior_count]!==value)rx_bad=rx_bad+1;
 end
 checks=checks+1;
 if(frame_error || overrun_error)begin control_bad=control_bad+1;end
end
endtask

task loopback_word;
input [DATA_WIDTH-1:0] value;
integer prior_count;
begin
 prior_count=rx_count;loopback=1;rx_ready=1;transmit_word(value,0);
 if(rx_count!=prior_count+1 || received[prior_count]!==value)loopback_bad=loopback_bad+1;
 checks=checks+1;loopback=0;peer_line=1;repeat(BAUD)tick();
end
endtask

task stress_checks;
reg [DATA_WIDTH-1:0] held;
integer prior_count,error_before,age;
begin
 reset_design();
 // Pending output is stable while the downstream consumer pauses; no second
 // serial frame arrives during this particular stability check.
 rx_ready=0;prior_count=rx_count;drive_serial(1,0);held=rx_data;
 if(!rx_valid || held!==1)rx_bad=rx_bad+1;checks=checks+1;
 repeat(BAUD*3)begin
  tick();if(rx_valid!==1 || rx_data!==held)$fatal(1,"RX_STABILITY pending output changed");checks=checks+1;
 end
 rx_ready=1;tick();
 if(rx_count!=prior_count+1 || received[prior_count]!==1)rx_bad=rx_bad+1;checks=checks+1;
 // Serial RX cannot backpressure its peer. A second completed frame while
 // output is pending reports overrun and replaces the one-word output buffer.
 rx_ready=0;drive_serial(1,0);error_before=overrun_errors;
 drive_serial(1<<(DATA_WIDTH-1),0);
 if(overrun_errors!=error_before+1 || !rx_valid || rx_data!==(1<<(DATA_WIDTH-1)))
  control_bad=control_bad+1;
 checks=checks+1;rx_ready=1;tick();
 // Invalid stop must raise framing error and must not publish a byte.
 reset_design();prior_count=rx_count;error_before=frame_errors;drive_serial(8'h35,1);
 if(frame_errors<=error_before || rx_count!=prior_count)control_bad=control_bad+1;checks=checks+1;
 // Asynchronous reset interrupts an in-flight transmitter and receiver.
 reset_design();wait_tx_ready();tx_data=8'h61;tx_valid=1;tick();tx_valid=0;
 peer_line=0;repeat(BAUD*2)tick();rst=1;#1;
 if(txd!==1 || tx_busy!==0 || rx_valid!==0)control_bad=control_bad+1;checks=checks+1;
 tick();rst=0;peer_line=1;repeat(BAUD*3)tick();
 transmit_word(1,1);receive_word(1<<(DATA_WIDTH-1));
end
endtask

initial begin
 if(DATA_WIDTH<5 || DATA_WIDTH>8 || PRESCALE<1 || PRESCALE>8 || WORDS<1 || WORDS>64)
  $fatal(1,"HARNESS unsupported UART profile");
 reset_design();
 for(n=0;n<3;n=n+1)loopback_word(word_value(n));
 $display("UART_LOOPBACK_RESULT frames=3 failures=%0d",loopback_bad);
 if(!LOOPBACK_ONLY)begin
  for(n=0;n<WORDS;n=n+1)transmit_word(word_value(n),1);
  for(n=0;n<WORDS;n=n+1)receive_word(word_value(n));
  if(STRESS)stress_checks();
 end
 $display("UART_SUMMARY tx_mismatches=%0d rx_mismatches=%0d loopback_mismatches=%0d control_mismatches=%0d checks=%0d",tx_bad,rx_bad,loopback_bad,control_bad,checks);
 if(tx_bad || rx_bad || loopback_bad || control_bad)
  $fatal(1,"UART_PEER_CONTRACT_FAILED independent LSB-first serial peer disagrees");
 begin $display("RTLREFINE_PASS nonce=2798ca86f3e3f6de91995375e05bcdbd checks=%0d", (checks)); $finish; end;
end
endmodule
