`timescale 1ns/1ps
`include "rtlrefine_check.vh"
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
    `RTLREFINE_DONE(checks);
end
endmodule
