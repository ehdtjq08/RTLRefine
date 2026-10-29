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
