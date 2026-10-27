`timescale 1ns/1ps
`include "rtlrefine_check.vh"
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
    `RTLREFINE_DONE(checks);
end
endmodule
