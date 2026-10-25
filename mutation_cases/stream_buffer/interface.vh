// SPDX-License-Identifier: MIT
module stream_buffer #(
    parameter ADDR_WIDTH = 2,
    parameter DATA_WIDTH = 8
)(
    input wire clk,
    input wire rst,
    input wire [DATA_WIDTH-1:0] s_data,
    input wire s_valid,
    output wire s_ready,
    input wire s_last,
    input wire s_user,
    output wire [DATA_WIDTH-1:0] m_data,
    output wire m_valid,
    input wire m_ready,
    output wire m_last,
    output wire m_user
);
