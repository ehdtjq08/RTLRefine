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




module tb_audit;
reg clk=0,rst=0,s_valid=0,m_ready=0;
reg [3:0] s_data=0;
wire s_ready,m_valid;
wire [3:0] m_data;
reg [3:0] queue[0:255];
integer head=0,tail=0,checks=0,i;
packet_queue dut(.*);
task tick;
reg take_in,take_out;
begin
    #1;
    if(rst) begin head=0;tail=0; end
    if(m_valid !== (!rst && tail!=head)) $fatal(1,"Audit valid mismatch");
    if(s_ready !== (!rst && ((tail-head<4) || (tail!=head && m_ready)))) $fatal(1,"Audit ready mismatch");
    take_in=!rst && s_valid && s_ready;take_out=!rst && m_valid && m_ready;
    if(take_out) begin
        if(m_data!==queue[head]) $fatal(1,"Audit FIFO order mismatch");
        head=head+1;
    end
    if(take_in) begin queue[tail]=s_data;tail=tail+1;end
    checks=checks+1;#1;clk=1;#1;clk=0;#1;
end
endtask
initial begin
    rst=1;tick();rst=0;
    for(i=0;i<64;i=i+1) begin
        rst=(i==23 || i==47);s_valid=(i%5!=0);m_ready=(i%7>1);
        s_data=i;tick();
    end
    begin $display("RTLREFINE_PASS nonce=8143b9dc2565378fb6ded49efcd40849 checks=%0d", (checks)); $finish; end;
end
endmodule
