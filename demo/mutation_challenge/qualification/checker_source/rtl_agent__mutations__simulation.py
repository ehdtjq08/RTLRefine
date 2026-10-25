"""Independent Python deque oracle observing only candidate interface transfers."""
from __future__ import annotations

from collections import deque
import random

from ..common import sha256, write_json
from .contract import AUDIT, DISCOVERY

FIELDS = ("cycle", "rst", "s_valid", "s_ready", "s_data", "s_last", "s_user", "m_valid", "m_ready", "m_data", "m_last", "m_user")


def vectors(profile):
    if profile not in DISCOVERY + AUDIT:
        raise ValueError("Unknown frozen stimulus profile")
    address_width, seed, cycles = profile
    rng = random.Random(seed)
    data = []
    for cycle in range(cycles):
        reset = cycle < 4 or cycle in (6, 7, 57, 58, 131, 132, 211)
        valid = rng.randrange(5) != 0
        ready = rng.randrange(4) != 0
        if 4 <= cycle < 6:
            valid, ready = True, False
        if 8 <= cycle < 20:
            valid, ready = True, True
        if 24 <= cycle < 40:
            valid, ready = True, False
        if 40 <= cycle < 52:
            valid, ready = True, cycle % 3 == 0
        if cycle >= cycles - ((1 << address_width) * 4 + 20):
            valid, ready, reset = False, True, False
        data.append({"rst": int(reset), "s_valid": int(valid), "s_data": rng.randrange(256),
                     "s_last": int(cycle % 7 == 1), "s_user": int(cycle % 5 in (1, 2)), "m_ready": int(ready)})
    return data


def testbench(stimulus, address_width, *, exact=False):
    assignments = []
    for i, row in enumerate(stimulus):
        assignments.append(f"rst_vec[{i}]={row['rst']};valid_vec[{i}]={row['s_valid']};data_vec[{i}]=8'd{row['s_data']};last_vec[{i}]={row['s_last']};user_vec[{i}]={row['s_user']};ready_vec[{i}]={row['m_ready']};")
    drive = '''s_valid=valid_vec[i];s_data=data_vec[i];s_last=last_vec[i];s_user=user_vec[i];''' if exact else '''if(rst) begin s_valid=0;s_data=0;s_last=0;s_user=0;end
  else if(consumed || !s_valid) begin
   s_valid=valid_vec[i];s_data=data_vec[i];s_last=last_vec[i];s_user=user_vec[i];
  end'''
    return '''`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg rst=1,s_valid=0,s_last=0,s_user=0,m_ready=0;
reg [7:0] s_data=0;
wire s_ready,m_valid,m_last,m_user;wire [7:0] m_data;
stream_buffer #(.ADDR_WIDTH(''' + str(address_width) + '''),.DATA_WIDTH(8)) dut(.*);
reg rst_vec[0:''' + str(len(stimulus) - 1) + '''];
reg valid_vec[0:''' + str(len(stimulus) - 1) + '''];
reg [7:0] data_vec[0:''' + str(len(stimulus) - 1) + '''];
reg last_vec[0:''' + str(len(stimulus) - 1) + '''];
reg user_vec[0:''' + str(len(stimulus) - 1) + '''];
reg ready_vec[0:''' + str(len(stimulus) - 1) + '''];
reg consumed=0;
integer cycle=-1,observations,i;
always @(posedge clk) begin
 consumed=(!rst && s_valid && s_ready);
 if(cycle>=0) $fdisplay(observations,"%0d,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b",cycle,rst,s_valid,s_ready,s_data,s_last,s_user,m_valid,m_ready,m_data,m_last,m_user);
end
initial begin
 observations=$fopen("observed.csv","w");$dumpfile("trace.vcd");$dumpvars(0,tb);
''' + "\n".join(assignments) + '''
 for(i=0;i<''' + str(len(stimulus)) + ''';i=i+1) begin
  @(negedge clk);cycle=i;rst=rst_vec[i];m_ready=ready_vec[i];
  ''' + drive + '''
  @(posedge clk);
 end
 @(negedge clk);$fclose(observations);$finish;
end
initial begin #100000;$fatal(1,"Timed out");end
endmodule
'''


def parse_rows(path):
    result = []
    for line in path.read_text().splitlines():
        parts = line.split(",")
        if len(parts) != len(FIELDS):
            raise ValueError("Malformed interface observation")
        row = dict(zip(FIELDS, parts))
        row["cycle"] = int(row["cycle"])
        result.append(row)
    if not result:
        raise ValueError("No interface observations")
    return result


def score(rows, depth, *, require_drained=True):
    expected, violations = deque(), []
    coverage = {"accepted_inputs": 0, "accepted_outputs": 0, "full_stalls": 0, "simultaneous": 0, "flush_nonempty": 0}
    previous = None
    for row in rows:
        failures = []
        control_names = ("rst", "s_valid", "s_ready", "m_valid", "m_ready")
        if any(row[name] not in ("0", "1") for name in control_names):
            violations.append({"cycle": row["cycle"], "property": "defined_handshake", "observed": row})
            break
        r = {name: int(row[name]) for name in control_names}
        if previous is not None and previous["rst"] == "0" and row["rst"] == "0" and previous["s_valid"] == "1" and previous["s_ready"] == "0":
            if row["s_valid"] != "1" or any(row[k] != previous[k] for k in ("s_data", "s_last", "s_user")):
                raise ValueError("Stimulus violated the source-stability assumption")
        previous = row
        expected_valid = int(not r["rst"] and bool(expected))
        expected_ready = int(not r["rst"] and (len(expected) < depth or (bool(expected) and r["m_ready"])))
        if r["m_valid"] != expected_valid:
            failures.append({"property": "valid_matches_occupancy", "expected": expected_valid, "actual": r["m_valid"]})
        if r["s_ready"] != expected_ready:
            failures.append({"property": "ready_matches_capacity", "expected": expected_ready, "actual": r["s_ready"]})
        if r["rst"]:
            coverage["flush_nonempty"] += int(bool(expected))
            expected.clear()
        else:
            if len(expected) > depth:
                failures.append({"property": "capacity", "expected_max": depth, "actual": len(expected)})
            if expected and r["m_valid"]:
                bits = (row["m_data"], row["m_last"], row["m_user"])
                wanted = expected[0]
                if any(not set(v) <= {"0", "1"} for v in bits):
                    failures.append({"property": "defined_output", "actual": bits, "expected": wanted})
                else:
                    actual = tuple(int(v, 2) for v in bits)
                    if actual != wanted:
                        failures.append({"property": "data_order_sidebands", "expected": wanted, "actual": actual})
            pop = bool(r["m_valid"] and r["m_ready"])
            push = bool(r["s_valid"] and r["s_ready"])
            coverage["full_stalls"] += int(len(expected) == depth and not r["m_ready"])
            coverage["simultaneous"] += int(push and pop)
            if pop:
                coverage["accepted_outputs"] += 1
                if expected:
                    expected.popleft()
            if push:
                bits = (row["s_data"], row["s_last"], row["s_user"])
                if any(not set(v) <= {"0", "1"} for v in bits):
                    raise ValueError("Stimulus produced undefined accepted input")
                expected.append(tuple(int(v, 2) for v in bits))
                coverage["accepted_inputs"] += 1
        for failure in failures:
            violations.append({"cycle": row["cycle"], **failure, "observed": row})
    if require_drained and expected:
        violations.append({"cycle": rows[-1]["cycle"], "property": "eventual_drain_in_scheduled_window", "remaining_words": len(expected)})
    return {"passed": not violations, "violation_count": len(violations), "first_violations": violations[:8], "coverage": coverage}


def simulate(source, directory, runner, profile):
    address_width, seed, cycles = profile
    return execute(source, directory, runner, vectors(profile), address_width, profile={"addr_width": address_width, "seed": seed, "cycles": cycles})


def execute(source, directory, runner, stimulus, address_width, *, profile=None, replay=False, exact=False):
    directory.mkdir(parents=True, exist_ok=False)
    tb = testbench(stimulus, address_width, exact=exact)
    (directory / "candidate.v").write_text(source)
    (directory / "tb.v").write_text(tb)
    write_json(directory / "stimulus.json", stimulus)
    commands = [runner.run("compile_simulation", directory)]
    if commands[-1]["status"] != "PASS":
        raise ValueError("Candidate did not compile in the protected simulation")
    commands.append(runner.run("simulate", directory))
    if commands[-1]["status"] != "PASS":
        raise ValueError("Protected simulation did not finish")
    if (directory / "candidate.v").read_text() != source or (directory / "tb.v").read_text() != tb:
        raise ValueError("Candidate or protected testbench changed during execution")
    rows = parse_rows(directory / "observed.csv")
    if len(rows) != len(stimulus) or [r["cycle"] for r in rows] != list(range(len(stimulus))):
        raise ValueError("Incomplete protected cycle sequence")
    record = {**score(rows, 1 << address_width, require_drained=not replay), "profile": profile,
              "observations": rows, "commands": commands, "rtl_sha256": sha256(source.encode()),
              "testbench_sha256": sha256(tb.encode()), "oracle": "Independent Python deque driven only by accepted interface transfers; no fixed RTL"}
    write_json(directory / "simulation.json", record)
    return record
