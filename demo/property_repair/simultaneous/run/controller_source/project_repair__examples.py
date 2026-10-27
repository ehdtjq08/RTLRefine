"""Portable examples for the importer, not a whitelist of supported modules."""
import io
import json
import zipfile


def example_files(kind='wide_math'):
    if kind=='wide_math':
        sources={
            'rtl/word_math.sv':'''// RTLRefine importer example, MIT.
module word_math #(parameter integer WIDTH = 129)(
    input wire [WIDTH-1:0] a, b,
    output wire [WIDTH-1:0] result
);
function automatic [WIDTH-1:0] combine(input [WIDTH-1:0] lhs, rhs);
    combine = lhs - rhs;
endfunction
assign result = combine(a, b);
endmodule
''',
            'rtl/customer_top.sv':'''// RTLRefine importer example, MIT.
module customer_top #(parameter integer WIDTH = 129)(
    input wire [WIDTH-1:0] a, b,
    output wire [WIDTH-1:0] result
);
word_math #(.WIDTH(WIDTH)) math_unit(.a(a), .b(b), .result(result));
endmodule
'''}
        public='''`timescale 1ns/1ps
`include "rtlrefine_check.vh"
module tb_public;
reg [128:0] a, b;
wire [128:0] result;
integer checks=0;
customer_top #(.WIDTH(129)) dut(.a(a),.b(b),.result(result));
initial begin
    a=129'd5; b=129'd2; #1;
    if (result !== a+b) $fatal(1,"SUM mismatch actual=%h expected=%h",result,a+b);
    checks=checks+1;
    a=(129'd1 << 128); b=129'd3; #1;
    if (result !== a+b) $fatal(1,"WIDE mismatch actual=%h expected=%h",result,a+b);
    checks=checks+1;
    `RTLREFINE_DONE(checks);
end
endmodule
'''
        audit='''`timescale 1ns/1ps
`include "rtlrefine_check.vh"
module tb_audit;
reg [128:0] a, b;
wire [128:0] result;
integer checks=0;
integer i;
customer_top #(.WIDTH(129)) dut(.a(a),.b(b),.result(result));
initial begin
    for(i=0;i<40;i=i+1) begin
        a={1'b1,$random,$random,$random,$random};
        b={1'b0,$random,$random,$random,$random}; #1;
        if(result !== a+b) $fatal(1,"AUDIT sum mismatch");
        checks=checks+1;
    end
    `RTLREFINE_DONE(checks);
end
endmodule
'''
        name='129-bit multi-file math';top='customer_top';editable=['rtl/word_math.sv'];params={'WIDTH':129}
        contract='The combinational result must equal a+b modulo 2**WIDTH. Preserve module ports and configuration.'
    elif kind=='dual_clock':
        sources={'rtl/domain_ticks.sv':'''// RTLRefine importer example, MIT.
module domain_ticks #(parameter integer WIDTH=80)(
    input wire clk_a, clk_b, reset,
    output reg [WIDTH-1:0] count_a,
    output reg [WIDTH-1:0] count_b
);
always @(posedge clk_a or posedge reset) begin
    if(reset) count_a <= 0;
    else count_a <= count_a + 1;
end
always @(posedge clk_b or posedge reset) begin
    if(reset) count_b <= 0;
    else count_b <= count_b + 2;
end
endmodule
'''}
        public='''`timescale 1ns/1ps
`include "rtlrefine_check.vh"
module tb_public;
reg clk_a=0, clk_b=0, reset=0;
wire [79:0] count_a,count_b;
integer checks=0;
domain_ticks #(.WIDTH(80)) dut(.*);
initial begin
    #1;reset=1;#1;reset=0;
    #1;clk_a=1;#1;clk_a=0;
    if(count_a!==80'd1) $fatal(1,"A counter must increment once");
    checks=checks+1;
    #1;clk_b=1;#1;clk_b=0;
    if(count_b!==80'd1) $fatal(1,"B counter increments by the wrong amount actual=%h",count_b);
    checks=checks+1;
    `RTLREFINE_DONE(checks);
end
endmodule
'''
        audit='''`timescale 1ns/1ps
`include "rtlrefine_check.vh"
module tb_audit;
reg clk_a=0,clk_b=0,reset=0;
wire [79:0] count_a,count_b;
reg [79:0] want_a=0,want_b=0;
integer checks=0,i;
domain_ticks #(.WIDTH(80)) dut(.*);
initial begin
    #1;reset=1;#1;reset=0;
    for(i=0;i<25;i=i+1) begin
        #2;clk_b=1;want_b=want_b+1;#1;clk_b=0;
        if(i%3==0) begin #2;clk_a=1;want_a=want_a+1;#1;clk_a=0; end
        if(count_a!==want_a || count_b!==want_b) $fatal(1,"Clock-domain counter mismatch");
        checks=checks+1;
    end
    `RTLREFINE_DONE(checks);
end
endmodule
'''
        name='Two-clock user counters';top='domain_ticks';editable=['rtl/domain_ticks.sv'];params={'WIDTH':80}
        contract='Each counter increments by exactly one on its own clock edge and clears on reset. Simulation does not establish metastability/CDC safety.'
    else:raise ValueError('Unknown importer example')
    config={'schema_version':1,'name':name,'dut_top':top,'rtl_files':list(sources),'editable_files':editable,
        'include_files':[],'include_dirs':[],'data_files':[],'defines':{},'dut_parameters':params,'contract':contract,
        'tests':[{'id':'basic','top':'tb_public','files':['tests/public.sv'],'phase':'public','minimum_checks':2},
                 {'id':'stress','top':'tb_audit','files':['tests/audit.sv'],'phase':'audit','minimum_checks':20}]}
    return {**{p:v.encode() for p,v in sources.items()},'tests/public.sv':public.encode(),'tests/audit.sv':audit.encode(),
        'rtlrefine.json':(json.dumps(config,indent=2)+'\n').encode()}


def example_zip(kind='wide_math'):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in example_files(kind).items():archive.writestr(name,data)
    return buffer.getvalue()
