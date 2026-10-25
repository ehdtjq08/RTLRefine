"""Specification monitor: abstract shift queue, not a second FIFO implementation."""
from __future__ import annotations

import json
import re

from ..common import sha256, write_json
from .contract import FORMAL_PROFILES
from .simulation import execute

INPUTS = {"rst", "s_valid", "s_data", "s_last", "s_user", "m_ready"}


def monitor(address_width):
    return '''module property_top(
input clk,rst,input [7:0] s_data,input s_valid,s_last,s_user,m_ready,
input [3:0] watched_bit,
output s_ready,m_valid,m_last,m_user,output [7:0] m_data,
output property_valid,property_ready,property_payload,property_stable,property_capacity,
output [''' + str(address_width) + ''':0] expected_count);
localparam ADDR_WIDTH=''' + str(address_width) + ''';
localparam DEPTH=1<<ADDR_WIDTH;
stream_buffer #(.ADDR_WIDTH(ADDR_WIDTH),.DATA_WIDTH(8)) dut(
.clk(clk),.rst(rst),.s_data(s_data),.s_valid(s_valid),.s_ready(s_ready),.s_last(s_last),.s_user(s_user),
.m_data(m_data),.m_valid(m_valid),.m_ready(m_ready),.m_last(m_last),.m_user(m_user));

// A transaction-level shift queue, independent of the DUT's circular pointers.
reg spec_queue[0:DEPTH-1];
reg [ADDR_WIDTH:0] spec_count=0;
wire push=!rst && s_valid && s_ready;
wire pop=!rst && m_valid && m_ready;
wire [9:0] input_word={s_last,s_user,s_data};
wire [9:0] output_word={m_last,m_user,m_data};
wire selected_input=input_word[watched_bit];
integer i;
always @(posedge clk) begin
 if(rst) spec_count<=0;
 else begin
  if(pop) begin
   for(i=0;i<DEPTH-1;i=i+1) spec_queue[i]<=spec_queue[i+1];
  end
  if(push) spec_queue[spec_count-(pop ? 1'b1 : 1'b0)]<=selected_input;
  case({push,pop})
   2'b10:spec_count<=spec_count+1'b1;
   2'b01:spec_count<=spec_count-1'b1;
   default:spec_count<=spec_count;
  endcase
 end
end
reg past_valid=0,past_source_held=0,past_output_held=0;
reg [9:0] past_input=0,past_output=0;
reg [3:0] past_bit=0;
always @(posedge clk) begin
 past_valid<=1;
 past_source_held<=!rst && s_valid && !s_ready;
 past_output_held<=!rst && m_valid && !m_ready;
 past_input<=input_word;past_output<=output_word;past_bit<=watched_bit;
end
always @* begin
 if(!past_valid) assume(rst);
 assume(watched_bit<10);
 if(past_valid) assume(watched_bit==past_bit);
 if(past_source_held && !rst) begin assume(s_valid);assume(input_word==past_input);end
end
assign expected_count=spec_count;
assign property_valid=(m_valid==(!rst && spec_count!=0));
assign property_ready=(s_ready==(!rst && ((spec_count<DEPTH) || (spec_count!=0 && m_ready))));
assign property_payload=rst || spec_count==0 || (output_word[watched_bit]==spec_queue[0]);
assign property_stable=rst || !past_output_held || (m_valid && output_word==past_output);
assign property_capacity=(spec_count<=DEPTH);
always @* begin
 assert(property_valid);assert(property_ready);assert(property_payload);assert(property_stable);assert(property_capacity);
end
endmodule
'''


def selected_trace(path):
    # Yosys occasionally emits bad JSON escapes in internal names. Parse only
    # simple public interface/property records; never rewrite the raw artifact.
    allowed = INPUTS | {"m_data", "m_valid", "m_last", "m_user", "s_ready", "watched_bit", "expected_count",
                        "property_valid", "property_ready", "property_payload", "property_stable", "property_capacity"}
    signals = []
    for line in path.read_text().splitlines():
        match = re.search(r'"name"\s*:\s*"([^"\\]+)"', line)
        if match and match.group(1) in allowed:
            signals.append(json.loads(line.strip().rstrip(",")))
    if not signals:
        raise ValueError("No public input signals in counterexample")
    return {"signal": signals}


def decode_signal(signal):
    data = iter(signal.get("data", []))
    result, current = [], None
    for symbol in signal["wave"]:
        if symbol == ".":
            pass
        elif symbol == "=":
            text = next(data)
            current = int(text, 2) if text and set(text) <= {"0", "1"} else None
        elif symbol in "01":
            current = int(symbol)
        elif symbol == "4":
            if signal.get("data"):
                next(data)
            current = None
        else:
            raise ValueError("Unsupported waveform symbol")
        result.append(current)
    return result


def replay_vectors(trace, steps):
    decoded = {s["name"]: decode_signal(s) for s in trace["signal"] if s["name"] in INPUTS}
    if set(decoded) != INPUTS or any(len(v) != steps + 1 for v in decoded.values()):
        raise ValueError("Incomplete symbolic input witness")
    rows = []
    for index in range(1, steps + 1):
        row = {name: decoded[name][index] for name in INPUTS}
        if any(value is None for value in row.values()):
            raise ValueError("Undefined witness input")
        rows.append(row)
    return rows


def bounded(source, directory, runner, profile):
    if profile not in FORMAL_PROFILES:
        raise ValueError("Unknown frozen formal profile")
    address_width, steps = profile
    directory.mkdir(parents=True, exist_ok=False)
    wrapper = monitor(address_width)
    (directory / "candidate.v").write_text(source)
    (directory / "properties.v").write_text(wrapper)
    script = f'''read_verilog -formal -sv candidate.v properties.v
hierarchy -check -top property_top
proc
flatten
memory_map
opt
chformal -lower
sat -seq {steps} -set-assumes -prove-asserts -set-init-zero -set-def-inputs -timeout 45 -show-ports -dump_json counterexample.json -dump_vcd counterexample.vcd
'''
    (directory / "bounded.ys").write_text(script)
    command = runner.run("bounded", directory)
    log = (directory / "bounded.log").read_text()
    passed = command["status"] == "PASS" and "SAT proof finished - no model found: SUCCESS!" in log
    status = "BOUNDED_PROPERTY_PASS" if passed else "COUNTEREXAMPLE" if "SAT proof finished - model found: FAIL!" in log else "UNPROVEN"
    record = {"status": status, "profile": {"addr_width": address_width, "data_width": 8, "steps": steps},
              "rtl_sha256": sha256(source.encode()), "monitor_sha256": sha256(wrapper.encode()), "script_sha256": sha256(script.encode()),
              "command": command, "fixed_reference_rtl_used": False,
              "properties": ["valid_matches_occupancy", "ready_matches_capacity", "payload_order_sidebands", "output_stability", "capacity"],
              "payload_method": "One unconstrained selector held constant over the bound covers every one of the 10 payload/sideband bits",
              "assumptions": "First symbolic step resets; legal stable source while stalled; selector in 0..9 and constant. No assumptions force DUT ready or valid.",
              "initial_state": "Unspecified state bits start at zero; explicit register initializers are retained",
              "limitation": "Bounded two-state property check at fixed widths/depths; not unbounded correctness or a power-on/CDC proof"}
    if status == "COUNTEREXAMPLE":
        try:
            trace = selected_trace(directory / "counterexample.json")
            record["public_trace"] = trace
            stimulus = replay_vectors(trace, steps)
            replay = execute(source, directory / "replay", runner, stimulus, address_width, replay=True, exact=True,
                             profile={"source": "SAT input witness", "addr_width": address_width, "cycles": steps})
            record["replay"] = {"status": "CONTRACT_FAILURE_REPRODUCED" if not replay["passed"] else "NOT_REPRODUCED", **{k: replay[k] for k in ("violation_count", "first_violations")},
                                "scope": "Same external input sequence replayed in four-state Icarus and independent Python queue; unknown uninitialized memory can differ from SAT zero initialization"}
        except (ValueError, OSError, StopIteration, json.JSONDecodeError) as exc:
            record["replay"] = {"status": "REPLAY_UNAVAILABLE", "error": str(exc)}
    if (directory / "candidate.v").read_text() != source or (directory / "properties.v").read_text() != wrapper:
        raise ValueError("Protected property monitor or candidate changed")
    write_json(directory / "formal.json", record)
    return record
