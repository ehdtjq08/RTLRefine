"""Independent byte/frame oracle for the historical frame-FIFO full-pointer bug."""
from __future__ import annotations

import re

from ..common import ROOT, sha256, write_json
from .keep_case import output_frames

ASSETS = ROOT / "third_party/verilog_axis_frame"
VARIANTS = ("continuous", "initial_stall", "bursts")
STEPS = 12


def offered():
    return [{"data": (11 + 9 * i) % 256, "keep": 1, "last": int(i % 3 == 2),
             "id": (i // 3) % 4, "dest": (i // 3 + 1) % 4, "user": (i // 3) % 2}
            for i in range(24)]


def expected_frames():
    words = offered()
    return [{"bytes": [w["data"] for w in words[start:start + 3]],
             **{key: words[start][key] for key in ("id", "dest", "user")}}
            for start in range(0, 24, 3)]


def testbench(variant="initial_stall"):
    if variant not in VARIANTS:
        raise ValueError("Unknown frozen frame-FIFO regression")
    ready = {"continuous": "1'b1", "initial_stall": "cycle>=24", "bursts": "cycle>=16 && cycle%13>=6"}[variant]
    return f'''`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg rst=1;
reg [7:0] s_axis_tdata=0;
reg s_axis_tkeep=1,s_axis_tvalid=0,s_axis_tlast=0,s_axis_tuser=0,m_axis_tready=0;
reg [1:0] s_axis_tid=0,s_axis_tdest=0;
wire s_axis_tready,m_axis_tvalid,m_axis_tlast,m_axis_tuser,m_axis_tkeep;
wire [7:0] m_axis_tdata;
wire [1:0] m_axis_tid,m_axis_tdest;
wire status_overflow,status_bad_frame,status_good_frame;
axis_fifo #(.ADDR_WIDTH(2),.DATA_WIDTH(8),.KEEP_ENABLE(1),.KEEP_WIDTH(1),
.LAST_ENABLE(1),.ID_ENABLE(1),.ID_WIDTH(2),.DEST_ENABLE(1),.DEST_WIDTH(2),
.USER_ENABLE(1),.USER_WIDTH(1),.FRAME_FIFO(1),.DROP_BAD_FRAME(0),.DROP_WHEN_FULL(0)) dut(.*);
integer cycle=0,observations,statuses,i;
always @(negedge clk) begin
 if(rst) begin cycle=0;m_axis_tready=1;end
 else begin cycle=cycle+1;m_axis_tready=({ready});end
end
always @(posedge clk) begin
 $fdisplay(observations,"%0t,%0d,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b",
 $time,cycle,rst,s_axis_tvalid,s_axis_tready,s_axis_tdata,s_axis_tkeep,s_axis_tlast,s_axis_tid,s_axis_tdest,s_axis_tuser,
 m_axis_tvalid,m_axis_tready,m_axis_tdata,m_axis_tkeep,m_axis_tlast,m_axis_tid,m_axis_tdest,m_axis_tuser);
 $fdisplay(statuses,"%0d,%b,%b,%b,%b",cycle,rst,status_overflow,status_bad_frame,status_good_frame);
end
initial begin
 observations=$fopen("observed.csv","w");statuses=$fopen("status.csv","w");$dumpfile("trace.vcd");$dumpvars(0,tb);
 repeat(4) @(negedge clk);rst=0;
 for(i=0;i<24;i=i+1) begin
  s_axis_tdata=(11+9*i)%256;s_axis_tkeep=1;s_axis_tlast=(i%3==2);
  s_axis_tid=(i/3)%4;s_axis_tdest=(i/3+1)%4;s_axis_tuser=(i/3)%2;s_axis_tvalid=1;
  @(posedge clk);while(!s_axis_tready) @(posedge clk);
  @(negedge clk);s_axis_tvalid=0;
 end
 repeat(80) @(negedge clk);$fclose(observations);$fclose(statuses);$finish;
end
initial begin #10000;$fatal(1,"Timed out");end
endmodule
'''


def simulate(source, directory, runner, variant="initial_stall"):
    directory.mkdir(parents=True, exist_ok=False)
    tb = testbench(variant)
    (directory / "candidate.v").write_text(source)
    (directory / "tb.v").write_text(tb)
    commands = [runner.run("compile_simulation", directory)]
    if commands[-1]["status"] != "PASS":
        raise ValueError("Frame-FIFO regression did not compile")
    commands.append(runner.run("simulate", directory))
    if commands[-1]["status"] != "PASS":
        raise ValueError("Frame-FIFO regression did not finish")
    if (directory / "candidate.v").read_text() != source or (directory / "tb.v").read_text() != tb:
        raise ValueError("Protected source or stimulus changed")
    from .keep_case import parse_observations
    rows = parse_observations(directory / "observed.csv")
    inputs = [{key: int(row["input_" + key], 2) for key in ("data", "keep", "last", "id", "dest", "user")}
              for row in rows if not row["reset"] and row["input_valid"] and row["input_ready"]]
    actual, errors = output_frames(rows, 1)
    expected = expected_frames()
    statuses = []
    for line in (directory / "status.csv").read_text().splitlines():
        parts = line.split(",")
        if len(parts) != 5 or any(bit not in ("0", "1") for bit in parts[1:]):
            raise ValueError("Undefined FIFO status observation")
        statuses.append(dict(zip(("cycle", "reset", "overflow", "bad_frame", "good_frame"), map(int, parts))))
    bad_status = [row for row in statuses if not row["reset"] and (row["overflow"] or row["bad_frame"])]
    unstable = [{"previous_cycle": a["cycle"], "current_cycle": b["cycle"]}
                for a, b in zip(rows, rows[1:]) if not a["reset"] and not b["reset"] and a["valid"] and not a["ready"]
                and (not b["valid"] or any(a[k] != b[k] for k in ("data", "keep", "last", "id", "dest", "user")))]
    record = {"passed": inputs == offered() and actual == expected and not errors and not bad_status and not unstable,
              "variant": variant, "input_transfers": len(inputs), "input_actual": inputs, "expected_frames": expected, "actual_frames": actual,
              "expected_bytes": 24, "actual_bytes": sum(len(frame["bytes"]) for frame in actual),
              "errors": errors, "bad_status": bad_status, "unstable_output": unstable, "observations": rows, "statuses": statuses,
              "commands": commands, "rtl_sha256": sha256(source.encode()), "testbench_sha256": sha256(tb.encode()),
              "property": "Eight three-byte frames fit individually in a four-word frame FIFO; no loss, corruption or drop when DROP_WHEN_FULL=0 and receiver eventually drains"}
    write_json(directory / "simulation.json", record)
    return record


def bounded_compare(source, directory, runner):
    directory.mkdir(parents=True, exist_ok=False)
    reference = (ASSETS / "fixed_axis_fifo.v").read_text()
    (directory / "candidate.v").write_text(source)
    (directory / "golden.v").write_text(re.sub(r"\bmodule\s+axis_fifo\b", "module reference_frame_fifo", reference, count=1))
    instances = []
    for module, name, p in (("axis_fifo", "candidate", "c"), ("reference_frame_fifo", "golden", "g")):
        instances.append(f'''wire {p}_ready,{p}_valid,{p}_last,{p}_user,{p}_keep,{p}_overflow,{p}_bad,{p}_good;
wire [7:0] {p}_data;wire [1:0] {p}_id,{p}_dest;
{module} #(.ADDR_WIDTH(2),.DATA_WIDTH(8),.KEEP_ENABLE(1),.KEEP_WIDTH(1),
.LAST_ENABLE(1),.ID_ENABLE(1),.ID_WIDTH(2),.DEST_ENABLE(1),.DEST_WIDTH(2),
.USER_ENABLE(1),.USER_WIDTH(1),.FRAME_FIFO(1),.DROP_BAD_FRAME(0),.DROP_WHEN_FULL(0)) {name}(
.clk(clk),.rst(rst),.s_axis_tdata(s_axis_tdata),.s_axis_tkeep(s_axis_tkeep),.s_axis_tvalid(s_axis_tvalid),
.s_axis_tlast(s_axis_tlast),.s_axis_tid(s_axis_tid),.s_axis_tdest(s_axis_tdest),.s_axis_tuser(s_axis_tuser),
.m_axis_tready(m_axis_tready),.s_axis_tready({p}_ready),.m_axis_tvalid({p}_valid),.m_axis_tdata({p}_data),
.m_axis_tkeep({p}_keep),.m_axis_tlast({p}_last),.m_axis_tid({p}_id),.m_axis_tdest({p}_dest),.m_axis_tuser({p}_user),
.status_overflow({p}_overflow),.status_bad_frame({p}_bad),.status_good_frame({p}_good));''')
    wrapper = '''module miter(input clk,rst,input [7:0] s_axis_tdata,input s_axis_tkeep,s_axis_tvalid,s_axis_tlast,
input [1:0] s_axis_tid,s_axis_tdest,input s_axis_tuser,m_axis_tready);
''' + "\n".join(instances) + '''
always @* begin
assert(c_ready==g_ready);assert(c_valid==g_valid);
assert(c_overflow==g_overflow);assert(c_bad==g_bad);assert(c_good==g_good);
if(g_valid) begin
assert(c_keep==g_keep);assert(c_last==g_last);assert(c_id==g_id);assert(c_dest==g_dest);assert(c_user==g_user);
if(g_keep) assert(c_data==g_data);
end
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
chformal -lower
sat -seq {STEPS} -prove-asserts -set-init-def -set-def-inputs -set-at 1 rst 1 -set-at 1 s_axis_tvalid 0 -set-at 2 rst 0 -timeout 45 -show-ports -dump_json counterexample.json -dump_vcd counterexample.vcd
'''
    (directory / "bounded.ys").write_text(script)
    command = runner.run("bounded", directory)
    log = (directory / "bounded.log").read_text()
    passed = command["status"] == "PASS" and "SAT proof finished - no model found: SUCCESS!" in log
    status = "BOUNDED_PASS" if passed else "COUNTEREXAMPLE" if "SAT proof finished - model found: FAIL!" in log else "UNPROVEN"
    result = {"status": status, "steps": STEPS, "command": command, "compared_output_bits": 20,
              "rtl_sha256": sha256(source.encode()), "reference_sha256": sha256(reference.encode()),
              "script_sha256": sha256(script.encode()), "reference": "Historical maintainer fix, excluded from model prompts",
              "clock_model": "Single synchronous clock, one active edge per symbolic step",
              "reset_constraints": "Reset asserted at step 1, released at step 2; unconstrained thereafter",
              "limitation": "12-step two-state reference comparison, four-word 8-bit FRAME_FIFO instance, not an unbounded proof"}
    write_json(directory / "bounded.json", result)
    return result
