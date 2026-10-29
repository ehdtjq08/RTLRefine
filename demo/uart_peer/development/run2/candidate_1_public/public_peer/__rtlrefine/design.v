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
            end else if (bit_cnt > 1) begin
                bit_cnt <= bit_cnt - 1;
                prescale_reg <= (prescale << 3)-1;
                data_reg <= {rxd, data_reg[DATA_WIDTH-1:1]};
            end
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
