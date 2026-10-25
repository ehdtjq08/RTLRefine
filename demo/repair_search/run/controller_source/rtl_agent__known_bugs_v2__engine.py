"""Native, two-state public-port trace checking; no RTL oracle during admission."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil

from ..common import sha256, write_json
from .runner import BenchmarkRunner


def qualify_expected_file(path, outputs):
    """Mask invalid payloads and implementation-specific debug observations."""
    path = Path(path)
    temporary = path.with_suffix(".qualified.tmp")
    with path.open() as source, temporary.open("w") as destination:
        for line in source:
            values = line.split()
            if len(values) != len(outputs):
                raise ValueError("Incomplete expected output row")
            by_name = dict(zip(outputs, values))
            for i, name in enumerate(outputs):
                if name == "o_debug":
                    values[i] = "?"
                elif name == "frame_len" and by_name.get("frame_len_valid") != "1":
                    values[i] = "?"
                elif name == "o_wb_data" and by_name.get("o_wb_ack") != "1":
                    values[i] = "?"
                elif any(name.endswith(suffix) for suffix in ("_tdata", "_tkeep", "_tlast", "_tid", "_tdest", "_tuser")):
                    prefix = name.rsplit("_", 1)[0]
                    if by_name.get(prefix + "_tvalid") in (None, "?", "0"):
                        values[i] = "?"
            destination.write(" ".join(values) + "\n")
    temporary.replace(path)


def verify_frame_length_oracle(trace, ports):
    """Independent transaction/count model checks the reference on its domain."""
    if "monitor_axis_tkeep" not in trace["inputs"]:
        return {"applicable": False}
    count, valid, checked = 0, 0, 0
    with Path(trace["stimulus"]).open() as stim, Path(trace["expected"]).open() as expected:
        for cycle, (input_line, output_line) in enumerate(zip(stim, expected)):
            row = dict(zip(trace["inputs"], [int(v, 16) for v in input_line.split()]))
            outputs = dict(zip(trace["outputs"], output_line.split()))
            keep = row["monitor_axis_tkeep"]
            if keep & (keep + 1):
                raise ValueError("Noncontiguous TKEEP outside the corrected artifact's domain")
            if outputs["frame_len_valid"] != format(valid, "x"):
                raise ValueError("Reference valid pulse disagrees with independent model")
            if valid and int(outputs["frame_len"], 16) != count:
                raise ValueError("Reference length disagrees with independent byte count")
            checked += 1 + valid
            if row["rst"]:
                count, valid = 0, 0
            else:
                count = 0 if valid else count
                valid = 0
                if row["monitor_axis_tvalid"] and row["monitor_axis_tready"]:
                    count = (count + keep.bit_count()) % (1 << ports["frame_len"]["width"])
                    valid = row["monitor_axis_tlast"]
    return {"applicable": True, "independent_observations_checked": checked, "domain": "Contiguous low-order keep masks, valid/ready transfers and synchronous reset"}


def inspect(source, dependencies, top, directory, runner):
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "candidate.v").write_text(source)
    (directory / "dependencies.v").write_text(dependencies)
    (directory / "inspect.ys").write_text(f"read_verilog -sv candidate.v dependencies.v\nhierarchy -check -top {top}\nproc\nwrite_json interface.json\n")
    command = runner.run("inspect", directory, top)
    if command["status"] != "PASS":
        raise ValueError("Interface inspection failed: " + str(directory))
    module = json.loads((directory / "interface.json").read_text())["modules"][top]
    ports = {name: {"direction": port["direction"], "width": len(port["bits"])} for name, port in module["ports"].items()}
    if any(port["width"] > 64 or port["direction"] == "inout" for port in ports.values()):
        raise ValueError("Current frozen harness supports input/output ports <=64 bits")
    write_json(directory / "ports.json", ports)
    return ports


def encode_table(csv_file, ports, clock, input_path, expected_path):
    inputs = sorted(n for n, p in ports.items() if p["direction"] == "input" and n != clock)
    outputs = sorted(n for n, p in ports.items() if p["direction"] == "output")
    count, ignored = 0, []
    with Path(csv_file).open() as stream, input_path.open("w") as stimulus, expected_path.open("w") as expected:
        reader = csv.DictReader(stream, skipinitialspace=True)
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        missing = set(inputs) - set(reader.fieldnames)
        if missing:
            raise ValueError("Missing public input columns: " + str(missing))
        ignored = sorted(set(reader.fieldnames) - set(ports))
        for row in reader:
            if not any(str(v).strip() for k, v in row.items() if k):
                continue
            iv, ov = [], []
            for name in inputs:
                value = row[name].strip()
                if not value.isdecimal():
                    raise ValueError("Undefined public input in trace")
                integer = int(value)
                if integer >= 1 << ports[name]["width"]:
                    raise ValueError("Public input exceeds configured width")
                iv.append(format(integer, "x"))
            for name in outputs:
                value = row.get(name, "?").strip()
                ov.append(format(int(value), "x") if value.isdecimal() else "?")
            stimulus.write(" ".join(iv) + "\n")
            expected.write(" ".join(ov) + "\n")
            count += 1
    qualify_expected_file(expected_path, outputs)
    return {"cycles": count, "inputs": inputs, "outputs": outputs, "ignored_non_port_columns": ignored,
            "output_masking": "Payload/length/Wishbone data only when expected valid/ack; debug outputs ignored",
            "sampling": "Public outputs after setting current inputs and evaluating combinational logic, before rising clock edge"}


def harness(ports, clock, top):
    inputs = sorted(n for n, p in ports.items() if p["direction"] == "input" and n != clock)
    outputs = sorted(n for n, p in ports.items() if p["direction"] == "output")
    assigns = "\n".join(f"dut.{name}=input_values[{i}];" for i, name in enumerate(inputs))
    samples = ",".join(f"static_cast<uint64_t>(dut.{name})" for name in outputs)
    return '''#include "V''' + top + '''.h"
#include "verilated.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
int main(int argc,char** argv) {
 Verilated::commandArgs(argc,argv);Verilated::randReset(0);
 V''' + top + ''' dut;
 bool capture=argc==2 && std::string(argv[1])=="capture";
 std::ifstream stim("stimulus.hex"),oracle("expected.hex");
 std::ofstream observed;if(capture) observed.open("observed.hex");
 if(!stim || (!capture && !oracle)) return 3;
 std::string iline,eline;uint64_t cycle=0,errors=0,comparisons=0;
 std::vector<std::string> history;
 while(std::getline(stim,iline)) {
  if(iline.empty()) continue;
  uint64_t input_values[''' + str(len(inputs)) + '''];
  std::istringstream in(iline);in>>std::hex;
  for(auto &v:input_values) if(!(in>>v)) return 4;
  dut.''' + clock + '''=0;
''' + assigns + '''
  dut.eval();
  uint64_t output_values[]={''' + samples + '''};
  history.push_back(iline);if(history.size()>9) history.erase(history.begin());
  if(capture) { for(auto v:output_values) observed<<std::hex<<v<<" ";observed<<"\\n"; }
  else {
   if(!std::getline(oracle,eline)) return 5;
   std::istringstream expected(eline);std::string token;
   for(size_t j=0;j<''' + str(len(outputs)) + ''';j++) {
    if(!(expected>>token)) return 6;
    if(token=="?") continue;
    comparisons++;
    uint64_t want=std::stoull(token,nullptr,16);
    if(want!=output_values[j]) {
     if(errors<10) {
      std::cout<<"MISMATCH "<<std::dec<<cycle<<" "<<j<<" "<<std::hex<<want<<" "<<output_values[j]<<"\\n";
      std::cout<<"INPUT_WINDOW "<<std::dec<<(cycle+1-history.size());
      for(auto &h:history) std::cout<<" | "<<h;
      std::cout<<"\\n";
     }
     errors++;
    }
   }
  }
  dut.''' + clock + '''=1;dut.eval();
  dut.''' + clock + '''=0;dut.eval();cycle++;
 }
 dut.final();
 std::cout<<"SUMMARY "<<std::dec<<cycle<<" "<<errors<<" "<<comparisons<<"\\n";
 return 0;
}
'''


def compile_candidate(source, dependencies, ports, clock, top, directory, runner):
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "candidate.v").write_text(source)
    (directory / "dependencies.v").write_text(dependencies)
    (directory / "harness.cpp").write_text(harness(ports, clock, top))
    commands = [runner.run("translate", directory, top)]
    if commands[-1]["status"] == "PASS":
        commands.append(runner.run("build", directory, top))
    return commands


def run_trace(compiled, trace, top, runner, *, capture=False):
    stimulus = Path(trace["stimulus"])
    expected = Path(trace["expected"])
    shutil.copyfile(stimulus, compiled / "stimulus.hex")
    shutil.copyfile(expected, compiled / "expected.hex")
    command = runner.run("simulate", compiled, top, capture=capture)
    log = (compiled / "simulate.log").read_text()
    summary = next((line.split()[1:] for line in log.splitlines() if line.startswith("SUMMARY ")), None)
    violations = []
    window = []
    for line in log.splitlines():
        if line.startswith("MISMATCH "):
            _, cycle, index, want, actual = line.split()
            violations.append({"cycle": int(cycle), "port": trace["outputs"][int(index)], "expected": int(want, 16), "actual": int(actual, 16)})
        elif line.startswith("INPUT_WINDOW "):
            start, *samples = line[len("INPUT_WINDOW "):].split(" | ")
            window.append({"start_cycle": int(start), "inputs": trace["inputs"], "samples": [[int(token, 16) for token in sample.split()] for sample in samples]})
    cycles, errors, compared = map(int, summary) if summary else (0, 0, 0)
    passed = command["status"] == "PASS" and cycles == trace["cycles"] and (capture or compared > 0 and errors == 0)
    record = {"passed": passed, "cycles": cycles, "comparisons": compared, "mismatch_count": errors,
              "first_mismatches": violations, "input_windows": window, "command": command,
              "stimulus_sha256": sha256(stimulus.read_bytes()), "expected_sha256": sha256(expected.read_bytes()),
              "trace_label": trace["label"], "scope": "Fixed-configuration two-state cycle-exact expected trace agreement, not general protocol correctness or unbounded proof"}
    return record
