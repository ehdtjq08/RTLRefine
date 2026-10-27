"""Authored integration fixtures, explicitly distinct from historical bugs."""
import json

SOURCE='''// RTLRefine independent-property example. MIT; authored defect fixture.
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
            2'b11: count <= count + 1;
            default: count <= count;
        endcase
    end
end
endmodule
'''

SMOKE='''`timescale 1ns/1ps
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
'''

AUDIT='''`timescale 1ns/1ps
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
'''


def example_files(kind='simultaneous'):
    healthy=SOURCE.replace("2'b11: count <= count + 1;","2'b11: count <= count;")
    if kind=='simultaneous':source=SOURCE
    elif kind=='wrap':source=healthy.replace('read_ptr == DEPTH-1','read_ptr == DEPTH-2')
    elif kind=='reset':source=healthy.replace('read_ptr <= 0;','read_ptr <= read_ptr;')
    elif kind=='healthy':source=healthy
    else:raise ValueError('Unknown authored FIFO example')
    contract={'schema_version':1,'kind':'ready_valid_fifo','ports':{p:p for p in ['clk','rst','s_valid','s_ready','s_data','m_valid','m_ready','m_data']},
              'data_width':4,'depth':4,'discovery_steps':12,'audit_steps':[16,20]}
    project={'schema_version':1,'name':'FIFO '+kind+' · authored fixture','dut_top':'packet_queue',
             'rtl_files':['rtl/packet_queue.sv'],'editable_files':['rtl/packet_queue.sv'],
             'dut_parameters':{'WIDTH':4,'DEPTH':4},'contract':'Ready/valid FIFO with synchronous reset, ordered data, capacity four and full-cycle replacement.',
             'tests':[{'id':'smoke','phase':'public','top':'tb_smoke','files':['tests/smoke.sv']},
                      {'id':'sequence_audit','phase':'audit','top':'tb_audit','files':['tests/audit.sv']}]}
    return {'rtl/packet_queue.sv':source.encode(),'tests/smoke.sv':SMOKE.encode(),'tests/audit.sv':AUDIT.encode(),
            'rtlrefine.json':json.dumps(project,indent=2).encode(),'fifo_contract.json':json.dumps(contract,indent=2).encode()}
