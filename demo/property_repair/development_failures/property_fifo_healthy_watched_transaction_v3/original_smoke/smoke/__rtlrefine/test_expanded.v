// RTLRefine independent-property example. MIT; authored defect fixture.
module packet_queue #(parameter WIDTH=4, DEPTH=4)(
    input wire clk, rst,
    input wire s_valid,
    output wire s_ready,
    input wire [WIDTH-1:0] s_data,
    output wire m_valid,
    input wire m_ready,
    output wire [WIDTH-1:0] m_data
);
localparam PW=$clog2(DEPTH);
reg [WIDTH-1:0] memory [0:DEPTH-1];
reg [PW-1:0] write_ptr=0, read_ptr=0;
reg [PW:0] count=0;
assign m_valid = !rst && count != 0;
assign s_ready = !rst && (count < DEPTH || (m_valid && m_ready));
assign m_data = memory[read_ptr];
wire push = s_valid && s_ready;
wire pop = m_valid && m_ready;
always @(posedge clk) begin
    if (rst) begin
        write_ptr <= 0;
        read_ptr <= 0;
        count <= 0;
    end else begin
        if (push) begin
            memory[write_ptr] <= s_data;
            write_ptr <= write_ptr == DEPTH-1 ? 0 : write_ptr+1;
        end
        if (pop)
            read_ptr <= read_ptr == DEPTH-1 ? 0 : read_ptr+1;
        case ({push,pop})
            2'b10: count <= count + 1;
            2'b01: count <= count - 1;
            2'b11: count <= count;
            default: count <= count;
        endcase
    end
end
endmodule
`timescale 1ns/1ps




module tb_smoke;
reg clk=0,rst=0,s_valid=0,m_ready=0;
reg [3:0] s_data=0;
wire s_ready,m_valid;
wire [3:0] m_data;
integer checks=0;
packet_queue dut(.*);
task tick; begin #2;clk=1;#1;clk=0;#1; end endtask
initial begin
    rst=1;tick();rst=0;
    s_valid=1;s_data=4'h3;tick();s_valid=0;
    if(!m_valid || m_data!==4'h3) $fatal(1,"First word mismatch");
    checks=checks+1;m_ready=1;tick();m_ready=0;
    if(m_valid) $fatal(1,"Expected empty");checks=checks+1;
    s_valid=1;s_data=4'ha;tick();s_valid=0;
    if(!m_valid || m_data!==4'ha) $fatal(1,"Second word mismatch");
    checks=checks+1;m_ready=1;tick();m_ready=0;
    if(m_valid) $fatal(1,"Expected empty");checks=checks+1;
    begin $display("RTLREFINE_PASS nonce=31a524444deccafa4d924cfd80e360e3 checks=%0d", (checks)); $finish; end;
end
endmodule
