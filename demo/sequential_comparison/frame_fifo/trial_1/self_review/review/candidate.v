/*

Copyright (c) 2013-2018 Alex Forencich

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
 * AXI4-Stream FIFO
 */
module axis_fifo #
(
    parameter ADDR_WIDTH = 12,
    parameter DATA_WIDTH = 8,
    parameter KEEP_ENABLE = (DATA_WIDTH>8),
    parameter KEEP_WIDTH = (DATA_WIDTH/8),
    parameter LAST_ENABLE = 1,
    parameter ID_ENABLE = 0,
    parameter ID_WIDTH = 8,
    parameter DEST_ENABLE = 0,
    parameter DEST_WIDTH = 8,
    parameter USER_ENABLE = 1,
    parameter USER_WIDTH = 1,
    parameter FRAME_FIFO = 0,
    parameter USER_BAD_FRAME_VALUE = 1'b1,
    parameter USER_BAD_FRAME_MASK = 1'b1,
    parameter DROP_BAD_FRAME = 0,
    parameter DROP_WHEN_FULL = 0
)
(
    input  wire                   clk,
    input  wire                   rst,

    /*
     * AXI input
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
     * AXI output
     */
    output wire [DATA_WIDTH-1:0]  m_axis_tdata,
    output wire [KEEP_WIDTH-1:0]  m_axis_tkeep,
    output wire                   m_axis_tvalid,
    input  wire                   m_axis_tready,
    output wire                   m_axis_tlast,
    output wire [ID_WIDTH-1:0]    m_axis_tid,
    output wire [DEST_WIDTH-1:0]  m_axis_tdest,
    output wire [USER_WIDTH-1:0]  m_axis_tuser,

    /*
     * Status
     */
    output wire                   status_overflow,
    output wire                   status_bad_frame,
    output wire                   status_good_frame
);

localparam CLK_ENABLE = 1;
localparam RST_ENABLE = 1;
localparam LAST_OFFSET = DATA_WIDTH-1;
localparam KEEP_OFFSET = DATA_WIDTH - (KEEP_ENABLE ? KEEP_WIDTH : 0);
localparam ID_OFFSET = KEEP_OFFSET - (ID_ENABLE ? ID_WIDTH : 0);
localparam DEST_OFFSET = ID_OFFSET - (DEST_ENABLE ? DEST_WIDTH : 0);
localparam USER_OFFSET = DEST_OFFSET - (USER_ENABLE ? USER_WIDTH : 0);

localparam WIDTH = DATA_WIDTH;
localparam USER_WIDTH_INT = USER_ENABLE ? USER_WIDTH : 1;
localparam ID_WIDTH_INT = ID_ENABLE ? ID_WIDTH : 1;
localparam DEST_WIDTH_INT = DEST_ENABLE ? DEST_WIDTH : 1;

localparam KEEP_OFFSET_INT = KEEP_ENABLE ? KEEP_OFFSET : 0;
localparam LAST_OFFSET_INT = LAST_ENABLE ? LAST_OFFSET : 0;
localparam ID_OFFSET_INT = ID_ENABLE ? ID_OFFSET : 0;
localparam DEST_OFFSET_INT = DEST_ENABLE ? DEST_OFFSET : 0;
localparam USER_OFFSET_INT = USER_ENABLE ? USER_OFFSET : 0;

localparam DEST_WIDTH_INT = DEST_ENABLE ? DEST_WIDTH : 1;
localparam USER_WIDTH_INT = USER_ENABLE ? USER_WIDTH : 1;

localparam S_AXIS_TDATA_WIDTH = DATA_WIDTH;
localparam S_AXIS_TKEEP_WIDTH = KEEP_WIDTH;
localparam S_AXIS_TLAST_WIDTH = 1;
localparam S_AXIS_TID_WIDTH = ID_WIDTH;
localparam S_AXIS_TDEST_WIDTH = DEST_WIDTH;
localparam S_AXIS_TUSER_WIDTH = USER_WIDTH;

localparam M_AXIS_TDATA_WIDTH = DATA_WIDTH;
localparam M_AXIS_TKEEP_WIDTH = KEEP_WIDTH;
localparam M_AXIS_TLAST_WIDTH = 1;
localparam M_AXIS_TID_WIDTH = ID_WIDTH;
localparam M_AXIS_TDEST_WIDTH = DEST_WIDTH;
localparam M_AXIS_TUSER_WIDTH = USER_WIDTH;

localparam LAST_ENABLE_INT = LAST_ENABLE ? 1 : 0;
localparam ID_ENABLE_INT = ID_ENABLE ? 1 : 0;
localparam DEST_ENABLE_INT = DEST_ENABLE ? 1 : 0;
localparam USER_ENABLE_INT = USER_ENABLE ? 1 : 0;
localparam KEEP_ENABLE_INT = KEEP_ENABLE ? 1 : 0;

localparam DROP_WHEN_FULL_INT = DROP_WHEN_FULL ? 1 : 0;
localparam DROP_BAD_FRAME_INT = DROP_BAD_FRAME ? 1 : 0;
localparam FRAME_FIFO_INT = FRAME_FIFO ? 1 : 0;

// check configuration
initial begin
    if (FRAME_FIFO && !LAST_ENABLE) begin
        $error("Error: FRAME_FIFO set requires LAST_ENABLE set");
        $finish;
    end

    if (DROP_BAD_FRAME && !FRAME_FIFO) begin
        $error("Error: DROP_BAD_FRAME set requires FRAME_FIFO set");
        $finish;
    end

    if (DROP_WHEN_FULL && !FRAME_FIFO) begin
        $error("Error: DROP_WHEN_FULL set requires FRAME_FIFO set");
        $finish;
    end

    if (DROP_BAD_FRAME && (USER_BAD_FRAME_MASK & {USER_WIDTH{1'b1}}) == 0) begin
        $error("Error: Invalid USER_BAD_FRAME_MASK value");
        $finish;
    end
end

localparam KEEP_OFFSET = DATA_WIDTH;
localparam LAST_OFFSET = KEEP_OFFSET + (KEEP_ENABLE ? KEEP_WIDTH : 0);
localparam ID_OFFSET   = LAST_OFFSET + (LAST_ENABLE ? 1          : 0);
localparam DEST_OFFSET = ID_OFFSET   + (ID_ENABLE   ? ID_WIDTH   : 0);
localparam USER_OFFSET = DEST_OFFSET + (DEST_ENABLE ? DEST_WIDTH : 0);
localparam WIDTH       = USER_OFFSET + (USER_ENABLE ? USER_WIDTH : 0);

reg [ADDR_WIDTH:0] wr_ptr_reg = {ADDR_WIDTH+1{1'b0}}, wr_ptr_next;
reg [ADDR_WIDTH:0] wr_ptr_cur_reg = {ADDR_WIDTH+1{1'b0}}, wr_ptr_cur_next;
reg [ADDR_WIDTH:0] wr_addr_reg = {ADDR_WIDTH+1{1'b0}};
reg [ADDR_WIDTH:0] rd_ptr_reg = {ADDR_WIDTH+1{1'b0}}, rd_ptr_next;
reg [ADDR_WIDTH:0] rd_addr_reg = {ADDR_WIDTH+1{1'b0}};

reg [WIDTH-1:0] mem[(2**ADDR_WIDTH)-1:0];
reg [WIDTH-1:0] mem_read_data_reg;
reg mem_read_data_valid_reg = 1'b0, mem_read_data_valid_next;

wire [WIDTH-1:0] s_axis;

reg [WIDTH-1:0] m_axis_reg;
reg m_axis_tvalid_reg = 1'b0, m_axis_tvalid_next;

// full when first MSB different but rest same (committed pointers)
wire full = ((wr_ptr_reg[ADDR_WIDTH] != rd_ptr_reg[ADDR_WIDTH]) &&
             (wr_ptr_reg[ADDR_WIDTH-1:0] == rd_ptr_reg[ADDR_WIDTH-1:0]));
// empty when pointers match exactly
wire empty = wr_ptr_reg == rd_ptr_reg;
// overflow within packet (speculative vs committed)
wire full_cur = FRAME_FIFO ? ((wr_ptr_reg[ADDR_WIDTH] != wr_ptr_cur_reg[ADDR_WIDTH]) &&
                 (wr_ptr_reg[ADDR_WIDTH-1:0] == wr_ptr_cur_reg[ADDR_WIDTH-1:0])) : 1'b0;
// write full condition: speculative vs read pointer for FRAME_FIFO, else committed vs read
wire write_full = FRAME_FIFO ? ((wr_ptr_cur_reg[ADDR_WIDTH] != rd_ptr_reg[ADDR_WIDTH]) &&
                   (wr_ptr_cur_reg[ADDR_WIDTH-1:0] == rd_ptr_reg[ADDR_WIDTH-1:0])) :
                 ((wr_ptr_reg[ADDR_WIDTH] != rd_ptr_reg[ADDR_WIDTH]) &&
                  (wr_ptr_reg[ADDR_WIDTH-1:0] == rd_ptr_reg[ADDR_WIDTH-1:0]));

// control signals
reg write;
reg read;
reg store_output;

reg drop_frame_reg = 1'b0, drop_frame_next;
reg overflow_reg = 1'b0, overflow_next;
reg bad_frame_reg = 1'b0, bad_frame_next;
reg good_frame_reg = 1'b0, good_frame_next;

// FIX: backpressure when dropping a frame to prevent partial frame writes
assign s_axis_tready = (!write_full && !drop_frame_reg) || DROP_WHEN_FULL;

generate
    assign s_axis[DATA_WIDTH-1:0] = s_axis_tdata;
    if (KEEP_ENABLE) assign s_axis[KEEP_OFFSET +: KEEP_WIDTH] = s_axis_tkeep;
    if (LAST_ENABLE) assign s_axis[LAST_OFFSET]               = s_axis_tlast;
    if (ID_ENABLE)   assign s_axis[ID_OFFSET   +: ID_WIDTH]   = s_axis_tid;
    if (DEST_ENABLE) assign s_axis[DEST_OFFSET +: DEST_WIDTH] = s_axis_tdest;
    if (USER_ENABLE) assign s_axis[USER_OFFSET +: USER_WIDTH] = s_axis_tuser;
endgenerate

assign m_axis_tvalid = m_axis_tvalid_reg;

assign m_axis_tdata = m_axis_reg[DATA_WIDTH-1:0];
assign m_axis_tkeep = KEEP_ENABLE ? m_axis_reg[KEEP_OFFSET +: KEEP_WIDTH] : {KEEP_WIDTH{1'b1}};
assign m_axis_tlast = LAST_ENABLE ? m_axis_reg[LAST_OFFSET]               : 1'b1;
assign m_axis_tid   = ID_ENABLE   ? m_axis_reg[ID_OFFSET   +: ID_WIDTH]   : {ID_WIDTH{1'b0}};
assign m_axis_tdest = DEST_ENABLE ? m_axis_reg[DEST_OFFSET +: DEST_WIDTH] : {DEST_WIDTH{1'b0}};
assign m_axis_tuser = USER_ENABLE ? m_axis_reg[USER_OFFSET +: USER_WIDTH] : {USER_WIDTH{1'b0}};

assign status_overflow = overflow_reg;
assign status_bad_frame = bad_frame_reg;
assign status_good_frame = good_frame_reg;

// Write logic
always @* begin
    write = 1'b0;
    wr_ptr_next = wr_ptr_reg;
    wr_ptr_cur_next = wr_ptr_cur_reg;

    drop_frame_next = 1'b0;
    overflow_next = 1'b0;
    bad_frame_next = 1'b0;
    good_frame_next = 1'b0;

    if (s_axis_tvalid) begin
        // input data valid
        if (!write_full || DROP_WHEN_FULL) begin
            // not full, perform write
            if (!FRAME_FIFO) begin
                // normal FIFO mode
                write = 1'b1;
                wr_ptr_next = wr_ptr_reg + 1;
            end else begin
                // frame FIFO mode
                // FIX: if currently dropping a frame, don't write; wait for tlast
                if (drop_frame_reg) begin
                    if (s_axis_tlast) begin
                        // end of dropped frame, reset speculative pointer
                        wr_ptr_cur_next = wr_ptr_reg;
                        drop_frame_next = 1'b0;
                        overflow_next = 1'b1;
                    end
                end else begin
                    write = 1'b1;
                    wr_ptr_cur_next = wr_ptr_cur_reg + 1;
                    if (s_axis_tlast) begin
                        // end of frame
                        if (DROP_BAD_FRAME && (USER_BAD_FRAME_MASK & s_axis_tuser == USER_BAD_FRAME_VALUE)) begin
                            // bad packet, reset write pointer
                            wr_ptr_cur_next = wr_ptr_reg;
                            drop_frame_next = 1'b1;
                            bad_frame_next = 1'b1;
                        end else begin
                            // good packet, update write pointer
                            wr_ptr_next = wr_ptr_cur_reg + 1;
                            good_frame_next = 1'b1;
                        end
                    end
                end
            end
        end else if (write_full || full_cur || drop_frame_reg) begin
            // full (and DROP_WHEN_FULL=1), packet overflow, or currently dropping frame
            // drop frame
            drop_frame_next = 1'b1;
            if (s_axis_tlast) begin
                // end of frame, reset write pointer
                wr_ptr_cur_next = wr_ptr_reg;
                drop_frame_next = 1'b0;
                overflow_next = 1'b1;
            end
        end
    end
end

always @(posedge clk) begin
    if (rst) begin
        wr_ptr_reg <= {ADDR_WIDTH+1{1'b0}};
        wr_ptr_cur_reg <= {ADDR_WIDTH+1{1'b0}};

        drop_frame_reg <= 1'b0;
        overflow_reg <= 1'b0;
        bad_frame_reg <= 1'b0;
        good_frame_reg <= 1'b0;
    end else begin
        wr_ptr_reg <= wr_ptr_next;
        wr_ptr_cur_reg <= wr_ptr_cur_next;

        drop_frame_reg <= drop_frame_next;
        overflow_reg <= overflow_next;
        bad_frame_reg <= bad_frame_next;
        good_frame_reg <= good_frame_next;
    end

    if (FRAME_FIFO) begin
        wr_addr_reg <= wr_ptr_cur_next;
    end else begin
        wr_addr_reg <= wr_ptr_next;
    end

    if (write) begin
        mem[wr_addr_reg[ADDR_WIDTH-1:0]] <= s_axis;
    end
end

// Read logic
always @* begin
    read = 1'b0;

    rd_ptr_next = rd_ptr_reg;

    mem_read_data_valid_next = mem_read_data_valid_reg;

    if (store_output || !mem_read_data_valid_reg) begin
        // output data not valid OR currently being transferred
        if (!empty) begin
            // not empty, perform read
            read = 1'b1;
            mem_read_data_valid_next = 1'b1;
            rd_ptr_next = rd_ptr_reg + 1;
        end else begin
            // empty, invalidate
            mem_read_data_valid_next = 1'b0;
        end
    end
end

always @(posedge clk) begin
    if (read) begin
        mem_read_data_reg <= mem[rd_addr_reg[ADDR_WIDTH-1:0]];
    end
    rd_addr_reg <= rd_ptr_next;
end

// Output register
always @* begin
    store_output = 1'b0;

    m_axis_tvalid_next = m_axis_tvalid_reg;

    if (m_axis_tready || !m_axis_tvalid_reg) begin
        // output data not valid OR currently being transferred
        if (mem_read_data_valid_reg) begin
            // have data, send it
            store_output = 1'b1;
            m_axis_tvalid_next = 1'b1;
        end else begin
            // no data
            m_axis_tvalid_next = 1'b0;
        end
    end
end

always @(posedge clk) begin
    if (rst) begin
        m_axis_tvalid_reg <= 1'b0;
    end else begin
        m_axis_tvalid_reg <= m_axis_tvalid_next;
        if (store_output) begin
            m_axis_reg <= mem_read_data_reg;
        end
    end
end

endmodule