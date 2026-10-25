"""Independent clocked testbench and bounded reference-comparison harness."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import ROOT, sha256, write_json
from .runner import SequentialRunner

ASSETS = ROOT / "third_party/verilog_axis_reset"
EXPECTED = [(0x61, 0, 1), (0x92, 1, 0)]


def formal_source(source):
    # Yosys cannot lower two separate async-reset event inputs for one process.
    # Their OR is already the RTL reset condition; name that same OR explicitly.
    for clock in ("input_clk", "output_clk"):
        old = f"always @(posedge {clock} or posedge input_rst or posedge output_rst) begin"
        if source.count(old) != 1:
            raise ValueError("Unexpected reset synchronizer; formal normalization refused")
        source = source.replace(old, f"always @(posedge {clock} or posedge joint_rst) begin")
    if source.count("if (input_rst | output_rst) begin") != 2 or source.count("// reset synchronization") != 1:
        raise ValueError("Unexpected asynchronous reset logic")
    return source.replace("if (input_rst | output_rst) begin", "if (joint_rst) begin").replace(
        "// reset synchronization", "wire joint_rst = input_rst | output_rst;\n// reset synchronization")


def testbench(write_half=5, read_half=7, prefill=1):
    if (write_half, read_half, prefill) not in ((5, 7, 1), (7, 5, 3), (5, 11, 2)):
        raise ValueError("Unknown frozen clock/reset regression")
    return f'''`timescale 1ns/1ps
module tb;
reg input_clk=0, output_clk=0;
always #{write_half} input_clk=~input_clk;
always #{read_half} output_clk=~output_clk;
reg input_rst=1,output_rst=1;
reg [7:0] input_axis_tdata=0;
reg input_axis_tvalid=0,input_axis_tlast=0,input_axis_tuser=0,output_axis_tready=0;
wire input_axis_tready,output_axis_tvalid,output_axis_tlast,output_axis_tuser;
wire [7:0] output_axis_tdata;
axis_async_fifo #(.ADDR_WIDTH(2),.DATA_WIDTH(8)) dut(.*);
integer phase=0, observations, i;
task send;
input [7:0] data;
input last,user;
begin
    @(negedge input_clk);
    input_axis_tdata=data;input_axis_tlast=last;input_axis_tuser=user;input_axis_tvalid=1;
    while(!input_axis_tready) @(negedge input_clk);
    @(posedge input_clk);
    @(negedge input_clk);input_axis_tvalid=0;
end
endtask
always @(posedge output_clk) begin
    $fdisplay(observations,"%0t,%0d,%b,%b,%b,%b,%b,%b,%b",$time,phase,input_rst,output_rst,
        output_axis_tvalid,output_axis_tready,output_axis_tdata,output_axis_tlast,output_axis_tuser);
end
initial begin
    observations=$fopen("observed.csv","w");
    $dumpfile("trace.vcd");$dumpvars(0,tb);
    #60; input_rst=0;output_rst=0;
    repeat(8) @(negedge input_clk);
    phase=1;
    for(i=0;i<{prefill};i=i+1) send(8'ha5+i,1,0);
    repeat(8) @(negedge output_clk);
    phase=2;
    input_rst=1;output_rst=1;
    repeat(6) @(negedge input_clk);
    input_rst=0;output_rst=0;
    repeat(8) @(negedge output_clk);
    phase=3;output_axis_tready=1;
    repeat(10) @(negedge output_clk);
    phase=4;
    send(8'h61,0,1);send(8'h92,1,0);
    repeat(20) @(negedge output_clk);
    $fclose(observations);$finish;
end
initial begin #10000;$fatal(1,"Timed out");end
endmodule
'''


def parse_observations(path):
    rows = []
    for line in path.read_text().splitlines():
        fields = line.split(",")
        if len(fields) != 9:
            raise ValueError("Malformed simulator observation")
        time, phase = map(int, fields[:2])
        rst_in, rst_out, valid, ready, data, last, user = fields[2:]
        if any(bit not in ("0", "1") for bit in (rst_in, rst_out, valid, ready)):
            raise ValueError("Undefined clock/reset/handshake observation")
        rows.append({"time_ps": time, "phase": phase, "input_reset": int(rst_in), "output_reset": int(rst_out),
                     "valid": int(valid), "ready": int(ready), "data_bits": data, "last_bits": last, "user_bits": user})
    if not rows or {row["phase"] for row in rows} != set(range(5)):
        raise ValueError("Simulator did not complete all protected phases")
    return rows


def simulate(source, directory, runner, variant=(5, 7, 1)):
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "candidate.v").write_text(source)
    tb = testbench(*variant)
    (directory / "tb.v").write_text(tb)
    commands = [runner.run("compile_simulation", directory)]
    if commands[-1]["status"] != "PASS":
        raise ValueError("Sequential testbench did not compile")
    commands.append(runner.run("simulate", directory))
    if commands[-1]["status"] != "PASS":
        raise ValueError("Sequential simulation did not finish")
    if (directory / "candidate.v").read_text() != source or (directory / "tb.v").read_text() != tb:
        raise ValueError("Protected source or testbench changed during execution")
    rows = parse_observations(directory / "observed.csv")
    stale = [row for row in rows if row["phase"] == 3 and row["valid"] and row["ready"]]
    fresh = [row for row in rows if row["phase"] == 4 and row["valid"] and row["ready"]]
    expected_bits = [(f"{value:08b}", str(last), str(user)) for value, last, user in EXPECTED]
    actual = [(row["data_bits"], row["last_bits"], row["user_bits"]) for row in fresh]
    record = {"passed": not stale and actual == expected_bits, "stale_transfers": stale,
              "fresh_expected": EXPECTED, "fresh_actual": actual, "variant": variant,
              "rtl_sha256": sha256(source.encode()), "testbench_sha256": sha256(tb.encode()),
              "commands": commands, "observations": rows,
              "property": "Reset flushes pre-reset data; subsequent traffic retains data/order/sidebands"}
    write_json(directory / "simulation.json", record)
    return record


def bounded_compare(source, directory, runner, steps=16):
    if steps not in (12, 16, 24, 40):
        raise ValueError("Unsupported frozen proof depth")
    directory.mkdir(parents=True, exist_ok=False)
    reference = (ASSETS / "fixed_axis_async_fifo.v").read_text()
    golden = re.sub(r"\bmodule\s+axis_async_fifo\b", "module reference_fifo", formal_source(reference), count=1)
    (directory / "candidate.v").write_text(formal_source(source))
    (directory / "golden.v").write_text(golden)
    wrapper = '''module miter(
input input_clk,output_clk,input_rst,output_rst,
input [7:0] input_axis_tdata,
input input_axis_tvalid,input_axis_tlast,input_axis_tuser,output_axis_tready);
wire c_ready,c_valid,c_last,c_user,g_ready,g_valid,g_last,g_user;
wire [7:0] c_data,g_data;
axis_async_fifo #(.ADDR_WIDTH(2),.DATA_WIDTH(8)) candidate(
.input_clk(input_clk),.output_clk(output_clk),.input_rst(input_rst),.output_rst(output_rst),
.input_axis_tdata(input_axis_tdata),.input_axis_tvalid(input_axis_tvalid),.input_axis_tlast(input_axis_tlast),
.input_axis_tuser(input_axis_tuser),.output_axis_tready(output_axis_tready),
.input_axis_tready(c_ready),.output_axis_tvalid(c_valid),.output_axis_tdata(c_data),.output_axis_tlast(c_last),.output_axis_tuser(c_user));
reference_fifo #(.ADDR_WIDTH(2),.DATA_WIDTH(8)) golden(
.input_clk(input_clk),.output_clk(output_clk),.input_rst(input_rst),.output_rst(output_rst),
.input_axis_tdata(input_axis_tdata),.input_axis_tvalid(input_axis_tvalid),.input_axis_tlast(input_axis_tlast),
.input_axis_tuser(input_axis_tuser),.output_axis_tready(output_axis_tready),
.input_axis_tready(g_ready),.output_axis_tvalid(g_valid),.output_axis_tdata(g_data),.output_axis_tlast(g_last),.output_axis_tuser(g_user));
always @* begin
assert(c_ready==g_ready);
assert(c_valid==g_valid);
if(g_valid) begin assert(c_data==g_data);assert(c_last==g_last);assert(c_user==g_user);end
end
endmodule
'''
    (directory / "miter.v").write_text(wrapper)
    script = f'''read_verilog -formal -sv candidate.v golden.v miter.v
hierarchy -check -top miter
proc
flatten
memory_map
opt
clk2fflogic
opt
sat -seq {steps} -prove-asserts -set-init-def -timeout 45 -show-ports -dump_json counterexample.json -dump_vcd counterexample.vcd
'''
    (directory / "bounded.ys").write_text(script)
    command = runner.run("bounded", directory)
    log = (directory / "bounded.log").read_text()
    passed = "SAT proof finished - no model found: SUCCESS!" in log
    failed = "SAT proof finished - model found: FAIL!" in log
    status = "BOUNDED_PASS" if passed and command["status"] == "PASS" else "COUNTEREXAMPLE" if failed else "UNPROVEN"
    result = {"status": status, "steps": steps, "command": command,
              "clock_model": "Independent symbolic clock levels, edge detection via clk2fflogic",
              "reference": "Historical upstream fix; excluded from model prompt", "rtl_sha256": sha256(source.encode()),
              "reference_sha256": sha256(reference.encode()), "script_sha256": sha256(script.encode()),
              "compared_output_bits": 12, "data_comparison": "Payload and sidebands compared only when reference valid",
              "normalization": "Name the existing input_rst | output_rst expression as joint_rst for the two reset synchronizers",
              "limitation": "Bounded two-state reference comparison, not an unbounded proof or CDC/metastability sign-off"}
    write_json(directory / "bounded.json", result)
    return result
