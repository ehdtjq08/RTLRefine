"""Bounded CTS safety over arbitrary BREAK/reset timing, without golden RTL."""
from __future__ import annotations

import json
import re

from ..common import sha256, write_json
from ..mutations.formal import decode_signal
from .contract import FORMAL
from .simulation import FIELDS, parse


def monitor(baud):
    return '''module property_top(input i_clk,i_reset,i_break,
output o_busy,o_uart_tx,property_blocked,output [3:0] age);
txuart #(.INITIAL_SETUP(31'd''' + str(baud) + ''')) dut(
.i_clk(i_clk),.i_reset(i_reset),.i_setup(31'd''' + str(baud) + '''),
.i_break(i_break),.i_wr(1'b0),.i_data(8'd0),.i_cts_n(1'b1),
.o_busy(o_busy),.o_uart_tx(o_uart_tx));
reg [3:0] stable_age=0;
reg past_valid=0;
always @(posedge i_clk) begin
 past_valid<=1;
 if(stable_age<15) stable_age<=stable_age+1'b1;
end
always @* if(!past_valid) assume(i_reset);
assign age=stable_age;
assign property_blocked=(stable_age<8) || o_busy;
always @* assert(property_blocked);
endmodule
'''


def selected_trace(path, steps):
    allowed = {"i_reset", "i_break", "o_busy", "o_uart_tx", "property_blocked", "age"}
    signals = []
    for line in path.read_text().splitlines():
        match = re.search(r'"name"\s*:\s*"([^"\\]+)"', line)
        if match and match.group(1) in allowed:
            signals.append(json.loads(line.strip().rstrip(",")))
    decoded = {s["name"]: decode_signal(s) for s in signals}
    if any(name not in decoded or len(decoded[name]) != steps + 1 for name in ("i_reset", "i_break")):
        raise ValueError("Incomplete UART input witness")
    inputs = [{name: decoded[name][i] for name in ("i_reset", "i_break")} for i in range(1, steps + 1)]
    if any(value not in (0, 1) for row in inputs for value in row.values()):
        raise ValueError("Undefined UART witness input")
    return {"signal": signals}, inputs


def replay(source, directory, runner, baud, inputs):
    directory.mkdir()
    (directory / "candidate.v").write_text(source)
    lines = []
    for i, row in enumerate(inputs):
        lines.append(f"step({i},{row['i_reset']},{row['i_break']});")
    bench = '''module tb;
reg i_clk=0,i_reset=0,i_break=0;
wire o_busy,o_uart_tx;
txuart #(.INITIAL_SETUP(31'd''' + str(baud) + ''')) dut(
.i_clk(i_clk),.i_reset(i_reset),.i_setup(31'd''' + str(baud) + '''),
.i_break(i_break),.i_wr(1'b0),.i_data(8'd0),.i_cts_n(1'b1),
.o_busy(o_busy),.o_uart_tx(o_uart_tx));
task step;
input integer cycle,rst,brk;
reg pre_busy,pre_tx;
begin
i_clk=0;i_reset=rst;i_break=brk;
#5;pre_busy=o_busy;pre_tx=o_uart_tx;i_clk=1;
#1;$display("UART %0d 0 %0d %0d 1 0 0 %b %b %b %b",cycle,rst,brk,pre_busy,pre_tx,o_busy,o_uart_tx);
#4;i_clk=0;
end
endtask
initial begin
''' + "\n".join(lines) + '\n$finish;end\nendmodule\n'
    (directory / "tb.v").write_text(bench)
    commands = [runner.run("compile_simulation", directory)]
    if commands[-1]["status"] == "PASS":
        commands.append(runner.run("simulate", directory))
    record = {"status": "REPLAY_UNAVAILABLE", "commands": commands, "exact_external_inputs": inputs,
              "scope": "Same top-level reset/BREAK inputs, fixed blocked CTS, four-state Icarus; not identical internal initial state"}
    if len(commands) == 2 and commands[-1]["status"] == "PASS":
        rows = parse((directory / "simulate.log").read_text())
        if len(rows) != len(inputs) or [r["cycle"] for r in rows] != list(range(len(inputs))):
            raise ValueError("Incomplete UART replay observations")
        for row, given in zip(rows, inputs):
            if row["reset"] != given["i_reset"] or row["break"] != given["i_break"]:
                raise ValueError("Replay input changed")
        failures = [row for row in rows if row["cycle"] >= 8 and row["busy_after"] != 1]
        record.update({"status": "CONTRACT_FAILURE_REPRODUCED" if failures else "NOT_REPRODUCED",
                       "violation_count": len(failures), "first_violations": failures[:8]})
        write_json(directory / "observations.json", rows)
    write_json(directory / "replay.json", record)
    return record


def bounded(source, directory, runner, profile):
    if profile not in FORMAL:
        raise ValueError("Unsupported UART formal profile")
    baud, steps = profile
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "candidate.v").write_text(source)
    wrapper = monitor(baud)
    (directory / "properties.v").write_text(wrapper)
    # Upstream FORMAL appendix is parsed with FORMAL *undefined*. Only our
    # external-port monitor is read with formal mode. It cannot constrain DUT.
    script = f'''read_verilog -sv candidate.v
read_verilog -formal -sv properties.v
hierarchy -check -top property_top
proc
flatten
opt
chformal -lower
sat -seq {steps} -set-assumes -prove-asserts -set-init-zero -set-def-inputs -timeout 45 -show-ports -dump_json counterexample.json -dump_vcd counterexample.vcd
'''
    (directory / "bounded.ys").write_text(script)
    command = runner.run("bounded", directory)
    log = (directory / "bounded.log").read_text()
    passed = command["status"] == "PASS" and "SAT proof finished - no model found: SUCCESS!" in log
    status = "BOUNDED_PROPERTY_PASS" if passed else "COUNTEREXAMPLE" if "SAT proof finished - model found: FAIL!" in log else "UNPROVEN"
    record = {"status": status, "profile": {"baud_cycles": baud, "steps": steps}, "command": command,
              "rtl_sha256": sha256(source.encode()), "monitor_sha256": sha256(wrapper.encode()), "fixed_reference_rtl_used": False,
              "property": "Continuously blocked active-low CTS keeps o_busy high after eight synchronizer warm-up clocks, including BREAK recovery",
              "assumptions": "First step resets. Setup constant, flow control enabled, CTS=1, write=0. Subsequent reset and BREAK arbitrary.",
              "initial_state": "Unspecified state bits zero; explicit upstream initial assignments retained",
              "limitation": "Bounded two-state CTS safety only. Serial-data behavior checked separately in simulations. Not unbounded, all-parameter or CDC proof."}
    if status == "COUNTEREXAMPLE":
        try:
            trace, inputs = selected_trace(directory / "counterexample.json", steps)
            record["public_trace"] = trace
            record["replay"] = replay(source, directory / "replay", runner, baud, inputs)
        except (ValueError, OSError, StopIteration, json.JSONDecodeError) as exc:
            record["replay"] = {"status": "REPLAY_UNAVAILABLE", "error": str(exc)}
    if (directory / "candidate.v").read_text() != source or (directory / "properties.v").read_text() != wrapper:
        raise ValueError("UART candidate or protected monitor changed")
    write_json(directory / "formal.json", record)
    return record
