"""Black-box UART/CTS checks from sampled external ports and serial bit frames."""
from __future__ import annotations

import random

from ..common import sha256, write_json


def setup_word(baud, bits, parity, stops, flow):
    parity_flags = {"none": 0, "odd": 1 << 26, "even": (1 << 26) | (1 << 24),
                    "mark": (1 << 26) | (1 << 25) | (1 << 24), "space": (1 << 26) | (1 << 25)}
    return baud | ((8 - bits) << 28) | ((stops - 1) << 27) | parity_flags[parity] | ((not flow) << 30)


def serial_bits(data, width, parity, stops):
    bits = [(data >> i) & 1 for i in range(width)]
    if parity != "none":
        bits.append({"even": sum(bits) % 2, "odd": 1 ^ (sum(bits) % 2), "mark": 1, "space": 0}[parity])
    return [0, *bits, *([1] * stops)]


def plan(profile):
    baud, bits, parity, stops, seed = profile
    rng = random.Random(seed)
    words = [0x00, 0xff, 0xa5, 0x61] + [rng.randrange(256) for _ in range(4)]
    rows = []
    def add(phase, count, reset=0, brk=0, cts=1, offer=0):
        rows.extend((phase, reset, brk, cts, offer) for _ in range(count))
    add(0, 3, reset=1)
    add(1, 16 * baud + 16) # ordinary startup, blocked receiver
    add(2, baud + 3, brk=1)
    add(3, 16 * baud + 16, offer=1) # one pending byte; legal write follows !busy
    add(4, 12, cts=0)
    add(5, (bits + stops + (parity != "none") + 5) * baud * len(words) + 80, cts=0, offer=1)
    add(6, 16, cts=1)
    add(7, baud + 5, brk=1)
    add(8, 16 * baud + 20, offer=1)
    add(9, 12, cts=0)
    add(10, (bits + stops + (parity != "none") + 5) * baud * len(words) + 80, cts=0, offer=1)
    add(11, 2, reset=1, cts=0)
    add(12, 16 * baud + 16, cts=0)
    add(13, (bits + stops + (parity != "none") + 5) * baud * len(words) + 80, cts=0, offer=1)
    add(14, 20, cts=0)
    return rows, words


def testbench(profile, flow):
    setup = setup_word(*profile[:4], flow)
    rows, words = plan(profile)
    commands = [f"step({i},{phase},{rst},{brk},{cts},{offer});" for i, (phase, rst, brk, cts, offer) in enumerate(rows)]
    initial_words = "\n".join(f"payload[{i}]=8'd{word};" for i, word in enumerate(words))
    return '''module tb;
reg i_clk=0,i_reset=0,i_break=0,i_wr=0,i_cts_n=1;
reg [7:0] i_data=0;
localparam [30:0] SETUP=31'd''' + str(setup) + ''';
wire o_busy,o_uart_tx;
txuart #(.INITIAL_SETUP(SETUP)) dut(.i_clk(i_clk),.i_reset(i_reset),.i_setup(SETUP),
 .i_break(i_break),.i_wr(i_wr),.i_data(i_data),.i_cts_n(i_cts_n),.o_busy(o_busy),.o_uart_tx(o_uart_tx));
reg [7:0] payload[0:7];
integer cursor=0,last_phase=-1;
task step;
input integer cycle,phase,rst,brk,cts,offer;
reg pre_busy,pre_tx;
begin
 i_clk=0;i_reset=rst;i_break=brk;i_cts_n=cts;
 if(phase!=last_phase && (phase==3 || phase==8 || phase==13)) cursor=0;
 last_phase=phase;
 i_data=payload[cursor%8];
 i_wr=offer && cursor<8 && !o_busy;
 #5;pre_busy=o_busy;pre_tx=o_uart_tx;
 i_clk=1;
 #1;$display("UART %0d %0d %0d %0d %0d %0d %0d %b %b %b %b",cycle,phase,rst,brk,cts,i_wr,i_data,pre_busy,pre_tx,o_busy,o_uart_tx);
 if(i_wr && !pre_busy && !rst && !brk) cursor=cursor+1;
 #4;i_clk=0;
end
endtask
initial begin
''' + initial_words + "\n" + "\n".join(commands) + '\n$finish;\nend\nendmodule\n'


FIELDS = ("cycle", "phase", "reset", "break", "cts_n", "write", "data", "busy_before", "tx_before", "busy_after", "tx_after")


def parse(log):
    rows = []
    for line in log.splitlines():
        if line.startswith("UART "):
            values = line.split()[1:]
            if len(values) != len(FIELDS):
                raise ValueError("Incomplete UART observation")
            rows.append({key: int(value) if value.isdecimal() else None for key, value in zip(FIELDS, values)})
    return rows


def check(rows, profile, flow):
    baud, width, parity, stops, _ = profile
    violations, accepted, frames, expected = [], [], [], None
    blocked_age = 0
    progress = {phase: 0 for phase in (5, 10, 13)}
    frame_index = 0
    def fail(row, kind, **details):
        violations.append({"cycle": row["cycle"], "phase": row["phase"], "kind": kind, **details})
    for row in rows:
        blocked_age = blocked_age + 1 if row["cts_n"] == 1 else 0
        if any(row[key] is None for key in FIELDS):
            fail(row, "unknown_external_port")
            continue
        if flow and blocked_age >= 8 and not row["reset"]:
            if row["busy_after"] != 1:
                fail(row, "ready_while_receiver_blocks", observed_busy=row["busy_after"])
            if row["write"] and not row["busy_before"] and not row["break"]:
                fail(row, "byte_accepted_while_receiver_blocks", data=row["data"])
        if row["reset"] or row["break"]:
            expected = None
            if row["reset"] and row["tx_after"] != 1:
                fail(row, "reset_output_not_idle")
            if row["break"] and row["tx_after"] != 0:
                fail(row, "break_not_asserted")
            continue
        if row["write"] and not row["busy_before"]:
            if expected is not None:
                fail(row, "accepted_before_previous_frame_finished")
            expected = {"start": row["cycle"], "bits": serial_bits(row["data"], width, parity, stops), "data": row["data"]}
            frame_index += 1
            accepted.append({"cycle": row["cycle"], "phase": row["phase"], "data": row["data"], "cts_n": row["cts_n"]})
            if row["phase"] in progress:
                progress[row["phase"]] += 1
        if expected is not None:
            age = row["cycle"] - expected["start"]
            bit = age // baud
            if bit < len(expected["bits"]):
                if row["tx_after"] != expected["bits"][bit]:
                    fail(row, "serial_bit_mismatch", frame=frame_index, bit=bit, data=expected["data"],
                         expected=expected["bits"][bit], actual=row["tx_after"])
            if age + 1 == len(expected["bits"]) * baud:
                frames.append({"start_cycle": expected["start"], "data": expected["data"], "bits": expected["bits"]})
                expected = None
    # Every pending byte must have completed; suppressing all writes cannot pass.
    for phase in (5, 10, 13):
        expected_count = 8
        if phase in (5, 10):
            previous = 3 if phase == 5 else 8
            expected_count -= sum(row["phase"] == previous for row in accepted)
        if progress[phase] != expected_count:
            violations.append({"phase": phase, "kind": "forward_progress_failed", "expected_accepts": expected_count, "actual_accepts": progress[phase]})
    if len(frames) != len(accepted):
        violations.append({"kind": "incomplete_serial_frames", "accepted": len(accepted), "completed": len(frames)})
    return {"passed": not violations, "violation_count": len(violations), "first_violations": violations[:12],
            "coverage": {"accepted_bytes": len(accepted), "complete_serial_frames": len(frames),
                         "blocked_receiver_accepts": sum(row["cts_n"] == 1 for row in accepted),
                         "released_receiver_accepts": sum(row["cts_n"] == 0 for row in accepted),
                         "break_cycles": sum(row["break"] for row in rows), "reset_cycles": sum(row["reset"] for row in rows)},
            "accepted": accepted, "decoded_frames": frames}


def simulate(source, directory, runner, profile, flow):
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "candidate.v").write_text(source)
    bench = testbench(profile, flow)
    (directory / "tb.v").write_text(bench)
    commands = [runner.run("compile_simulation", directory)]
    if commands[-1]["status"] == "PASS":
        commands.append(runner.run("simulate", directory))
    record = {"passed": False, "profile": {"baud_cycles": profile[0], "data_bits": profile[1], "parity": profile[2],
              "stop_bits": profile[3], "seed": profile[4], "flow_control": flow}, "commands": commands,
              "rtl_sha256": sha256(source.encode()), "bench_sha256": sha256(bench.encode()), "fixed_reference_rtl_used": False}
    if len(commands) == 2 and commands[-1]["status"] == "PASS":
        rows = parse((directory / "simulate.log").read_text())
        expected_rows = len(plan(profile)[0])
        if len(rows) != expected_rows or [r["cycle"] for r in rows] != list(range(expected_rows)):
            raise ValueError("Missing, duplicate or reordered UART observations")
        write_json(directory / "observations.json", rows)
        record.update(check(rows, profile, flow))
    else:
        record.update({"violation_count": 1, "first_violations": [{"kind": "tool_failed", "stage": commands[-1]["stage"]}]})
    write_json(directory / "simulation.json", record)
    return record
