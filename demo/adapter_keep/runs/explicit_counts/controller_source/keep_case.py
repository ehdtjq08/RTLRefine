"""Byte-stream oracle for the real axis_adapter disabled-TKEEP bug."""
from __future__ import annotations

import json
import re

from ..common import ROOT, sha256, write_json

ASSETS = ROOT / "third_party/verilog_axis_adapter_keep"
VARIANTS = ((8, False, "bursts"), (16, False, "bursts"), (32, False, "bursts"),
            (8, True, "continuous"), (16, True, "bursts"), (32, True, "bursts"))
PROOF_CONFIGS = ((8, False), (16, False), (32, False), (16, True))
STEPS = 20


def offered(keep_enabled):
    return [{"data": (7 + 13 * i) % 256, "keep": int(i % 5 != 2) if keep_enabled else 0,
             "last": int(i % 5 == 4), "id": i // 5, "dest": (i // 5 + 1) % 4, "user": (i // 5) % 2}
            for i in range(20)]


def expected_frames(keep_enabled):
    words = offered(keep_enabled)
    return [{"bytes": [w["data"] for w in words[start:start + 5] if not keep_enabled or w["keep"]],
             "id": words[start]["id"], "dest": words[start]["dest"], "user": words[start]["user"]}
            for start in range(0, 20, 5)]


def testbench(width, keep_enabled, pattern):
    if (width, keep_enabled, pattern) not in VARIANTS:
        raise ValueError("Unknown frozen byte-validity regression")
    ready = "1'b1" if pattern == "continuous" else "cycle >= 10 && cycle % 13 >= 5"
    keep = "i%5!=2" if keep_enabled else "1'b0"
    return f'''`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg rst=1;
reg [7:0] s_axis_tdata=0;
reg s_axis_tkeep=0,s_axis_tvalid=0,s_axis_tlast=0,s_axis_tuser=0,m_axis_tready=0;
reg [1:0] s_axis_tid=0,s_axis_tdest=0;
wire s_axis_tready,m_axis_tvalid,m_axis_tlast,m_axis_tuser;
wire [{width-1}:0] m_axis_tdata;
wire [{width//8-1}:0] m_axis_tkeep;
wire [1:0] m_axis_tid,m_axis_tdest;
axis_adapter #(.S_DATA_WIDTH(8),.S_KEEP_ENABLE({int(keep_enabled)}),.S_KEEP_WIDTH(1),
.M_DATA_WIDTH({width}),.M_KEEP_ENABLE(1),.M_KEEP_WIDTH({width//8}),
.ID_ENABLE(1),.ID_WIDTH(2),.DEST_ENABLE(1),.DEST_WIDTH(2),.USER_ENABLE(1),.USER_WIDTH(1)) dut(.*);
integer cycle=0,observations,i;
always @(negedge clk) begin
 if(rst) begin cycle=0;m_axis_tready=0;end
 else begin cycle=cycle+1;m_axis_tready=({ready});end
end
always @(posedge clk) begin
 $fdisplay(observations,"%0t,%0d,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b",
 $time,cycle,rst,s_axis_tvalid,s_axis_tready,s_axis_tdata,s_axis_tkeep,s_axis_tlast,s_axis_tid,s_axis_tdest,s_axis_tuser,
 m_axis_tvalid,m_axis_tready,m_axis_tdata,m_axis_tkeep,m_axis_tlast,m_axis_tid,m_axis_tdest,m_axis_tuser);
end
initial begin
 observations=$fopen("observed.csv","w");$dumpfile("trace.vcd");$dumpvars(0,tb);
 repeat(4) @(negedge clk);rst=0;
 for(i=0;i<20;i=i+1) begin
  s_axis_tdata=(7+13*i)%256;s_axis_tkeep=({keep});s_axis_tlast=(i%5==4);
  s_axis_tid=i/5;s_axis_tdest=(i/5+1)%4;s_axis_tuser=(i/5)%2;s_axis_tvalid=1;
  @(posedge clk);while(!s_axis_tready) @(posedge clk);
  @(negedge clk);s_axis_tvalid=0;
  if(i%4==1) repeat(2) @(negedge clk);
 end
 repeat(80) @(negedge clk);$fclose(observations);$finish;
end
initial begin #10000;$fatal(1,"Timed out");end
endmodule
'''


def parse_observations(path):
    keys = ("time_ps", "cycle", "reset", "input_valid", "input_ready", "input_data", "input_keep", "input_last", "input_id", "input_dest", "input_user",
            "valid", "ready", "data", "keep", "last", "id", "dest", "user")
    rows = []
    for line in path.read_text().splitlines():
        parts = line.split(",")
        if len(parts) != len(keys):
            raise ValueError("Malformed AXI adapter observation")
        row = dict(zip(keys, parts))
        for key in ("time_ps", "cycle"):
            row[key] = int(row[key])
        for key in ("reset", "input_valid", "input_ready", "valid", "ready"):
            if row[key] not in ("0", "1"):
                raise ValueError("Undefined handshake/reset observation")
            row[key] = int(row[key])
        # Ignore invalid payload bits; every accepted word must be fully defined.
        for prefix in ("input_", ""):
            if not row["reset"] and row[prefix + "valid"] and row[prefix + "ready"]:
                for field in ("data", "keep", "last", "id", "dest", "user"):
                    if not set(row[prefix + field]) <= {"0", "1"}:
                        raise ValueError("Undefined accepted data or sideband")
        rows.append(row)
    if len(rows) < 80 or not any(row["reset"] for row in rows):
        raise ValueError("Protected stimulus did not complete")
    return rows


def output_frames(rows, lanes):
    frames, payload, metadata, errors = [], [], None, []
    for row in rows:
        if row["reset"] or not row["valid"] or not row["ready"]:
            continue
        current = {name: int(row[name], 2) for name in ("id", "dest", "user")}
        if metadata is None:
            metadata = current
        elif metadata != current:
            errors.append("Frame sidebands changed")
        value, keep = int(row["data"], 2), int(row["keep"], 2)
        payload.extend((value >> (8 * lane)) & 255 for lane in range(lanes) if keep & (1 << lane))
        if int(row["last"], 2):
            frames.append({"bytes": payload, **metadata})
            payload, metadata = [], None
    if metadata is not None:
        errors.append("Unterminated output frame")
    return frames, errors


def simulate(source, directory, runner, variant=VARIANTS[1]):
    width, keep_enabled, pattern = variant
    tb = testbench(width, keep_enabled, pattern)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "candidate.v").write_text(source)
    (directory / "tb.v").write_text(tb)
    commands = [runner.run("compile_simulation", directory)]
    if commands[-1]["status"] != "PASS":
        raise ValueError("AXI adapter regression did not compile")
    commands.append(runner.run("simulate", directory))
    if commands[-1]["status"] != "PASS":
        raise ValueError("AXI adapter regression did not finish")
    if (directory / "candidate.v").read_text() != source or (directory / "tb.v").read_text() != tb:
        raise ValueError("Protected source or testbench changed")
    rows = parse_observations(directory / "observed.csv")
    inputs = [{field: int(row["input_" + field], 2) for field in ("data", "keep", "last", "id", "dest", "user")}
              for row in rows if not row["reset"] and row["input_valid"] and row["input_ready"]]
    expected, (actual, errors) = expected_frames(keep_enabled), output_frames(rows, width // 8)
    unstable = []
    for previous, current in zip(rows, rows[1:]):
        if not previous["reset"] and not current["reset"] and previous["valid"] and not previous["ready"]:
            if not current["valid"] or any(previous[k] != current[k] for k in ("data", "keep", "last", "id", "dest", "user")):
                unstable.append({"previous_cycle": previous["cycle"], "current_cycle": current["cycle"]})
    record = {"passed": inputs == offered(keep_enabled) and actual == expected and not errors and not unstable,
              "variant": {"source_width": 8, "output_width": width, "source_keep_enabled": keep_enabled, "ready_pattern": pattern},
              "input_transfers": len(inputs), "input_actual": inputs, "expected_frames": expected, "actual_frames": actual,
              "expected_bytes": sum(len(f["bytes"]) for f in expected), "actual_bytes": sum(len(f["bytes"]) for f in actual),
              "errors": errors, "unstable_output": unstable, "observations": rows, "commands": commands,
              "rtl_sha256": sha256(source.encode()), "testbench_sha256": sha256(tb.encode()),
              "property": "Disabled source TKEEP means all input bytes valid. Preserve bytes, frame boundaries and sidebands through width conversion and stalls"}
    write_json(directory / "simulation.json", record)
    return record


def bounded_compare(source, directory, runner, config=PROOF_CONFIGS[1]):
    if config not in PROOF_CONFIGS:
        raise ValueError("Unsupported frozen adapter comparison")
    width, keep_enabled = config
    lanes = width // 8
    directory.mkdir(parents=True, exist_ok=False)
    reference = (ASSETS / "fixed_axis_adapter.v").read_text()
    (directory / "candidate.v").write_text(source)
    (directory / "golden.v").write_text(re.sub(r"\bmodule\s+axis_adapter\b", "module reference_adapter", reference, count=1))
    instances = []
    for module, name, p in (("axis_adapter", "candidate", "c"), ("reference_adapter", "golden", "g")):
        instances.append(f'''wire {p}_ready,{p}_valid,{p}_last,{p}_user;
wire [{width-1}:0] {p}_data;wire [{lanes-1}:0] {p}_keep;wire [1:0] {p}_id,{p}_dest;
{module} #(.S_DATA_WIDTH(8),.S_KEEP_ENABLE({int(keep_enabled)}),.S_KEEP_WIDTH(1),
.M_DATA_WIDTH({width}),.M_KEEP_ENABLE(1),.M_KEEP_WIDTH({lanes}),.ID_ENABLE(1),.ID_WIDTH(2),
.DEST_ENABLE(1),.DEST_WIDTH(2),.USER_ENABLE(1),.USER_WIDTH(1)) {name}(
.clk(clk),.rst(rst),.s_axis_tdata(s_axis_tdata),.s_axis_tkeep(s_axis_tkeep),.s_axis_tvalid(s_axis_tvalid),
.s_axis_tlast(s_axis_tlast),.s_axis_tid(s_axis_tid),.s_axis_tdest(s_axis_tdest),.s_axis_tuser(s_axis_tuser),
.m_axis_tready(m_axis_tready),.s_axis_tready({p}_ready),.m_axis_tvalid({p}_valid),.m_axis_tdata({p}_data),
.m_axis_tkeep({p}_keep),.m_axis_tlast({p}_last),.m_axis_tid({p}_id),.m_axis_tdest({p}_dest),.m_axis_tuser({p}_user));''')
    byte_assertions = "\n".join(f"if(g_keep[{i}]) assert(c_data[{i*8} +: 8]==g_data[{i*8} +: 8]);" for i in range(lanes))
    wrapper = '''module miter(input clk,rst,input [7:0] s_axis_tdata,input s_axis_tkeep,s_axis_tvalid,s_axis_tlast,
input [1:0] s_axis_tid,s_axis_tdest,input s_axis_tuser,m_axis_tready);
''' + "\n".join(instances) + '''
always @* begin
assert(c_ready==g_ready);assert(c_valid==g_valid);
if(g_valid) begin
assert(c_keep==g_keep);assert(c_last==g_last);assert(c_id==g_id);assert(c_dest==g_dest);assert(c_user==g_user);
''' + byte_assertions + '''
end
end
endmodule
'''
    (directory / "miter.v").write_text(wrapper)
    script = f'''read_verilog -formal -sv candidate.v golden.v miter.v
hierarchy -check -top miter
proc
flatten
opt
chformal -lower
sat -seq {STEPS} -prove-asserts -set-init-def -set-def-inputs -set-at 1 rst 1 -set-at 1 s_axis_tvalid 0 -set-at 2 rst 0 -timeout 45 -show-ports -dump_json counterexample.json -dump_vcd counterexample.vcd
'''
    (directory / "bounded.ys").write_text(script)
    command = runner.run("bounded", directory)
    log = (directory / "bounded.log").read_text()
    passed = command["status"] == "PASS" and "SAT proof finished - no model found: SUCCESS!" in log
    status = "BOUNDED_PASS" if passed else "COUNTEREXAMPLE" if "SAT proof finished - model found: FAIL!" in log else "UNPROVEN"
    result = {"status": status, "steps": STEPS, "config": {"source_width": 8, "output_width": width, "source_keep_enabled": keep_enabled},
              "command": command, "compared_output_bits": width + lanes + 8,
              "rtl_sha256": sha256(source.encode()), "reference_sha256": sha256(reference.encode()),
              "script_sha256": sha256(script.encode()), "reference": "Historical maintainer fix; evaluation-only, excluded from prompts",
              "clock_model": "Single synchronous clock; one active edge per symbolic step",
              "reset_constraints": "Reset asserted at step 1, released at step 2; unconstrained thereafter",
              "data_comparison": "Payload bytes compared only when reference valid and corresponding reference TKEEP bit set",
              "limitation": "20-step two-state reference comparison at the listed parameters; not an unbounded proof or coverage of all parameterizations"}
    write_json(directory / "bounded.json", result)
    return result


def messages(original, baseline, schema, feedback=None):
    system = '''Repair this Verilog 2001 AXI-stream width adapter with local edits.
S_KEEP_ENABLE=0 means the source has no byte-validity qualifier: all source bytes
are valid regardless of the value on s_axis_tkeep. M_KEEP_ENABLE=1 requires a
correct output byte-valid mask, including partially filled words at TLAST.
Preserve enabled-TKEEP behavior, frames, data, ID/DEST/USER and ready/valid flow.
The checks include same-width bypass and widening, with source TKEEP both
enabled and disabled. Keep license, module parameters, ports, directives and bus-width assertions
byte-identical. Do not add initial blocks, system tasks, timing delays, modules,
or testbench access. Return up to 12 exact before/after edits against the
ORIGINAL source, with before snippets <=600 and after <=1200 chars. Supply an
expected_matches integer for every edit. All and only those exact occurrences
will be replaced. For a shared assignment you may explicitly replace multiple
occurrences with a short snippet and the correct count. Counts must match.
No known patch or reference source is supplied. Independent simulation and a
bounded reference comparison will check the result.
Required JSON output schema:\n''' + json.dumps(schema)
    failure = {key: baseline[key] for key in ("variant", "input_transfers", "expected_frames", "actual_frames", "expected_bytes", "actual_bytes")}
    user = "Original RTL:\n" + original + "\nIndependent Icarus failure:\n" + json.dumps(failure)
    if feedback is not None:
        user += "\nPrevious proposal feedback; propose against the same original:\n" + json.dumps(feedback)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
