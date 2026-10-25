module axis_width_converter #(
    parameter int DATA_WIDTH = 8,
    parameter int KEEP_ENABLE = 0,
    parameter int ID_ENABLE = 0,
    parameter int DEST_ENABLE = 0,
    parameter int USER_ENABLE = 1,
    parameter int USER_WIDTH = 1,
    parameter int INPUT_WIDTH = 8,
    parameter int OUTPUT_WIDTH = 8,
    parameter int INPUT_KEEP_ENABLE = KEEP_ENABLE,
    parameter int OUTPUT_KEEP_ENABLE = KEEP_ENABLE
)
(
    input  logic                   clk,
    input  logic                   rst,
    /*
     * AXI stream input
     */
    input  logic [INPUT_WIDTH-1:0] input_tdata,
    input  logic                   input_tvalid,
    output logic                   input_tready,
    input  logic                   input_tlast,
    input  logic [USER_WIDTH-1:0]  input_tuser,
    input  logic                   input_tkeep,
    input  logic [id_width-1:0]    input_tid,
    input  logic [dest_width-1:0]  input_tdest,
    /*
     * AXI stream output
     */
    output logic [OUTPUT_WIDTH-1:0] output_tdata,
    output logic                   output_tvalid,
    input  logic                   output_tready,
    output logic                   output_tlast,
    output logic [USER_WIDTH-1:0]  output_tuser,
    output logic                   output_tkeep,
    output logic [id_width-1:0]    output_tid,
    output logic [dest_width-1:0]  output_tdest
);

localparam int id_width = ID_ENABLE ? 8 : 1;
localparam int dest_width = DEST_ENABLE ? 8 : 1;
localparam int user_width = USER_ENABLE ? USER_WIDTH : 1;
localparam int keep_width = (INPUT_KEEP_ENABLE || OUTPUT_KEEP_ENABLE) ? 1 : 1;

localparam int LCM = lcm(INPUT_WIDTH, OUTPUT_WIDTH);

localparam int INPUT_LANES = LCM / INPUT_WIDTH;
localparam int OUTPUT_LANES = LCM / OUTPUT_WIDTH;

localparam int INPUT_LANES_LD = clog2(INPUT_LANES);
localparam int OUTPUT_LANES_LD = clog2(OUTPUT_LANES);

localparam int input_lane_width = (INPUT_LANES > 1) ? INPUT_WIDTH : LCM;
localparam int output_lane_width = (OUTPUT_LANES > 1) ? OUTPUT_WIDTH : LCM;

logic [INPUT_LANES_LD-1:0] input_lane;
logic [OUTPUT_LANES_LD-1:0] output_lane;

logic [input_lane_width-1:0] input_tdata_int_reg = '0;
logic [user_width-1:0]       input_tuser_int_reg = '0;
logic                         input_tkeep_int_reg = '0;
logic [id_width-1:0]         input_tid_int_reg = '0;
logic [dest_width-1:0]       input_tdest_int_reg = '0;

logic [output_lane_width-1:0] output_tdata_int_reg = '0;
logic [user_width-1:0]        output_tuser_int_reg = '0;
logic                         output_tkeep_int_reg = '0;
logic [id_width-1:0]          output_tid_int_reg = '0;
logic [dest_width-1:0]        output_tdest_int_reg = '0;

logic input_tuser_int;
logic input_tkeep_int;
logic [id_width-1:0] input_tid_int;
logic [dest_width-1:0] input_tdest_int;

logic output_tuser_int;
logic output_tkeep_int;
logic [id_width-1:0] output_tid_int;
logic [dest_width-1:0] output_tdest_int;

logic input_tvalid_int;
logic output_tvalid_int;
logic output_tlast_int;

logic output_tlast_reg = 1'b0;

logic input_tkeep_int_early;
logic output_tkeep_int_early;

/*
 * Input valid when holding data internally
 */
assign input_tvalid_int = INPUT_KEEP_ENABLE ?
    (INPUT_WIDTH >= OUTPUT_WIDTH) ?
        (output_tkeep_int_reg ? 1'b0 : 1'b1) |
        (output_lane != OUTPUT_LANES-1 ? 1'b1 : 1'b0) :
        (input_tkeep_int_reg ? 1'b0 : 1'b1) |
        (input_lane != INPUT_LANES-1 ? 1'b1 : 1'b0) :
    (INPUT_WIDTH >= OUTPUT_WIDTH) ?
        (output_lane != OUTPUT_LANES-1 ? 1'b1 : 1'b0) :
        (input_lane > 0 ? 1'b1 : 1'b0);

assign output_tvalid_int = INPUT_KEEP_ENABLE ?
    (INPUT_WIDTH >= OUTPUT_WIDTH) ?
        (output_tkeep_int_reg ? 1'b1 : 1'b0) :
        (input_tkeep_int_reg ? 1'b1 : 1'b0) : 1'b0;

/* Fixed: input_tready uses inverted input_tvalid_int for non-KEEP case (matches original correct logic) */
assign input_tready = INPUT_KEEP_ENABLE ? (input_tvalid_int | output_tready) : (~input_tvalid_int | output_tready);

assign input_tuser_int = KEEP_ENABLE ? (input_tkeep_int_reg ? input_tuser_int_reg : input_tuser) : input_tuser;
assign input_tkeep_int = KEEP_ENABLE ? (input_tkeep_int_reg ? input_tkeep_int_reg : input_tkeep) : 1'b0;
assign input_tid_int = KEEP_ENABLE ? (input_tkeep_int_reg ? input_tid_int_reg : input_tid) : input_tid;
assign input_tdest_int = KEEP_ENABLE ? (input_tkeep_int_reg ? input_tdest_int_reg : input_tdest) : input_tdest;

assign output_tuser_int = KEEP_ENABLE ? (output_tkeep_int_reg ? output_tuser_int_reg : output_tuser) : input_tuser_int;
assign output_tkeep_int = KEEP_ENABLE ? (output_tkeep_int_reg ? output_tkeep_int_reg : output_tkeep) : 1'b0;
assign output_tid_int = KEEP_ENABLE ? (output_tkeep_int_reg ? output_tid_int_reg : output_tid) : input_tid_int;
assign output_tdest_int = KEEP_ENABLE ? (output_tkeep_int_reg ? output_tdest_int_reg : output_tdest) : input_tdest_int;

assign output_tuser = KEEP_ENABLE ? (output_tkeep_int_reg ? output_tuser_int_reg : input_tuser_int) : input_tuser_int;
assign output_tkeep = KEEP_ENABLE ? (output_tkeep_int_reg ? output_tkeep_int_reg : input_tkeep_int) : 1'b0;
assign output_tid = KEEP_ENABLE ? (output_tkeep_int_reg ? output_tid_int_reg : input_tid_int) : input_tid_int;
assign output_tdest = KEEP_ENABLE ? (output_tkeep_int_reg ? output_tdest_int_reg : input_tdest_int) : input_tdest_int;

assign output_tlast_int = INPUT_WIDTH >= OUTPUT_WIDTH ? (output_lane == OUTPUT_LANES-1) : input_tlast;

assign output_tlast = KEEP_ENABLE ? (output_tkeep_int_reg ? output_tlast_reg : output_tlast_int) : output_tlast_int;

/* Fixed: output_tvalid for widening case - only valid on last input lane */
assign output_tvalid = (INPUT_WIDTH < OUTPUT_WIDTH) ? (input_tvalid & (input_lane == INPUT_LANES-1)) : (input_tvalid | input_tvalid_int);

assign output_tdata = (INPUT_WIDTH >= OUTPUT_WIDTH) ?
    input_tdata_int_reg >> (output_lane * OUTPUT_WIDTH) :
    input_tdata | (input_tdata_int_reg << INPUT_WIDTH);

always_ff @(posedge clk) begin
    if (rst) begin
        input_lane <= '0;
        output_lane <= '0;
        output_tlast_reg <= 1'b0;
        input_tkeep_int_reg <= 1'b0;
        output_tkeep_int_reg <= 1'b0;
    end else begin
        /* input lane counter */
        if (input_tready & input_tvalid) begin
            if (INPUT_WIDTH < OUTPUT_WIDTH) begin
                input_lane <= input_lane + 1'b1;
            end
        end

        /* output lane counter */
        if (output_tready & output_tvalid) begin
            if (INPUT_WIDTH >= OUTPUT_WIDTH) begin
                output_lane <= output_lane + 1'b1;
            end
        end

        /* input register - FIXED: only load when not at last lane for widening */
        if (input_tready & input_tvalid & (INPUT_WIDTH < OUTPUT_WIDTH) & (input_lane != INPUT_LANES-1)) begin
            input_tdata_int_reg <= input_tdata;
            input_tuser_int_reg <= input_tuser_int;
            input_tkeep_int_reg <= input_tkeep_int;
            input_tid_int_reg <= input_tid_int;
            input_tdest_int_reg <= input_tdest_int;
        end

        /* output register */
        if (input_tready & input_tvalid & (INPUT_WIDTH >= OUTPUT_WIDTH)) begin
            output_tdata_int_reg <= input_tdata;
            output_tuser_int_reg <= input_tuser_int;
            output_tkeep_int_reg <= input_tkeep_int;
            output_tid_int_reg <= input_tid_int;
            output_tdest_int_reg <= input_tdest_int;
        end

        /* keep registers */
        input_tkeep_int_early <= KEEP_ENABLE && (input_tready & input_tvalid & input_tkeep_int);
        output_tkeep_int_early <= KEEP_ENABLE && (output_tready & output_tvalid & output_tkeep_int);

        if (!KEEP_ENABLE || !input_tkeep_int_early) begin
            input_tkeep_int_reg <= 1'b0;
        end

        if (!KEEP_ENABLE || !output_tkeep_int_early) begin
            output_tkeep_int_reg <= 1'b0;
        end

        output_tlast_reg <= output_tlast_int;
    end
end

endmodule