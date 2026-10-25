"""Qualify public historical regressions before selecting any model outcome."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import shutil
import tomllib

from rtl_agent.common import ROOT, new_run_dir, sha256, write_json
from rtl_agent.known_bugs_v2.engine import inspect, encode_table, compile_candidate, run_trace, qualify_expected_file, verify_frame_length_oracle
from rtl_agent.known_bugs_v2.runner import BenchmarkRunner

UPSTREAM = ROOT / "research/known_bug_benchmark/upstream/benchmarks/fpga-debugging"
DATA = ROOT / "external_cases/known_bugs_v2"
CONTROLS = ROOT / "research/known_bug_benchmark/control_sources_v2"
SELECTED = ("axis-adapter-s3", "axis-async-fifo-c4", "axis-fifo-d12", "axis-frame-fifo-d11", "axis-frame-len-d13", "axis-switch-d8", "zipcpu-spi-c1-c3-d9")


def wrapper(project):
    # Project-authored wrappers reproduce the documented public parameterization;
    # no unlicensed wrapper text is copied from the research artifact.
    if project == "axis-async-fifo-c4":
        return '''// SPDX-License-Identifier: MIT
module bench_top(input clk,async_rst,input [7:0] input_axis_tdata,
input input_axis_tvalid,input_axis_tlast,input_axis_tuser,output input_axis_tready,
output [7:0] output_axis_tdata,output output_axis_tvalid,output output_axis_tlast,output output_axis_tuser,input output_axis_tready);
wire [7:0] data;wire valid,ready,last,user;
axis_register #(.DATA_WIDTH(8)) frontend(.clk(clk),.rst(async_rst),
.s_axis_tdata(input_axis_tdata),.s_axis_tvalid(input_axis_tvalid),.s_axis_tready(input_axis_tready),.s_axis_tlast(input_axis_tlast),.s_axis_tuser(input_axis_tuser),
.m_axis_tdata(data),.m_axis_tvalid(valid),.m_axis_tready(ready),.m_axis_tlast(last),.m_axis_tuser(user));
axis_async_fifo #(.ADDR_WIDTH(5),.DATA_WIDTH(8)) buffer(.async_rst(async_rst),
.input_clk(clk),.input_axis_tdata(data),.input_axis_tvalid(valid),.input_axis_tready(ready),.input_axis_tlast(last),.input_axis_tuser(user),
.output_clk(clk),.output_axis_tdata(output_axis_tdata),.output_axis_tvalid(output_axis_tvalid),.output_axis_tready(output_axis_tready),.output_axis_tlast(output_axis_tlast),.output_axis_tuser(output_axis_tuser));
endmodule
'''
    return ""


def dependencies(project, meta, edit_file):
    source_names = [name for name in meta["project"]["sources"] if name != edit_file and not name.endswith("wrapper.v")]
    content = "\n".join((UPSTREAM / project / name).read_text() for name in source_names)
    return content + "\n" + wrapper(project)


def transformed_trace(base, destination, ports, seed):
    rng = random.Random(seed)
    inputs = base["inputs"]
    # Additional inputs are generated before any model result is observed.
    masks = {}
    for name in inputs:
        if name.endswith("tdata") or name == "i_wb_data":
            # Preserve SPI command/config control bits; exercise low data bytes.
            width = min(ports[name]["width"], 8) if name == "i_wb_data" else ports[name]["width"]
            masks[name] = rng.randrange(1, 1 << width)
    destination.mkdir()
    source_path = Path(base["stimulus"])
    cycles = 0
    with (destination / "stimulus.hex").open("w") as out:
        if "monitor_axis_tkeep" in inputs:
            held, remaining = None, 1
            for cycle in range(256):
                reset = cycle in (0, 63, 127)
                ready = rng.randrange(2)
                if reset:
                    held = None
                if held is None and not reset and rng.random() < .8:
                    remaining = rng.randrange(1, 7) if remaining == 1 else remaining - 1
                    held = (((1 << rng.randrange(ports["monitor_axis_tkeep"]["width"] + 1)) - 1), int(remaining == 1))
                values = {"rst": int(reset), "monitor_axis_tvalid": int(held is not None and not reset),
                          "monitor_axis_tready": ready, "monitor_axis_tkeep": held[0] if held else 0,
                          "monitor_axis_tlast": held[1] if held else 0}
                out.write(" ".join(format(values[name], "x") for name in inputs) + "\n")
                if ready and held:
                    held = None
                cycles += 1
        else:
            epochs = 1 if "i_wb_data" in inputs else 8
            for epoch in range(epochs):
                epoch_masks = {name: rng.randrange(1, 1 << min(ports[name]["width"], 8 if name == "i_wb_data" else 64)) for name in masks}
                with source_path.open() as src:
                    for line in src:
                        values = [int(token, 16) for token in line.split()]
                        for i, name in enumerate(inputs):
                            if name in epoch_masks:
                                values[i] ^= epoch_masks[name]
                        out.write(" ".join(format(v, "x") for v in values) + "\n")
                        cycles += 1
    (destination / "expected.hex").write_text("")
    return {**base, "cycles": cycles, "stimulus": str(destination / "stimulus.hex"), "expected": str(destination / "expected.hex"),
            "label": f"unexposed_payload_transform_{seed}", "payload_xor_masks": masks,
            "oracle_origin": "Captured from the artifact's corrected control before inference, not an independently authored behavioral oracle"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", choices=SELECTED, action="append")
    args = parser.parse_args()
    projects = args.project or list(SELECTED)
    DATA.mkdir(parents=True, exist_ok=True)
    if (DATA / "FROZEN.json").exists():
        raise ValueError("Do not regenerate the dataset after inference has been frozen")
    CONTROLS.mkdir(parents=True, exist_ok=True)
    root = new_run_dir("known_bug_v2_qualification")
    print(str(root), flush=True)
    runner = BenchmarkRunner()
    ready, detail = runner.probe(root / "isolation")
    if not ready:
        raise RuntimeError(detail)
    rows = []
    for project in projects:
        original = UPSTREAM / project
        meta = tomllib.loads((original / "project.toml").read_text())
        for bug in meta["bugs"]:
            case_id = project + "_" + bug["name"]
            folder = root / case_id
            folder.mkdir()
            source = (original / bug["buggy"]).read_text()
            fixed = (original / bug["original"]).read_text()
            deps = dependencies(project, meta, bug["original"])
            top = "bench_top" if project == "axis-async-fifo-c4" else meta["project"]["toplevel"]
            record = {"id": case_id, "project": project, "bug": bug["name"], "qualified": False, "reason": None}
            try:
                ports = inspect(fixed, deps, top, folder / "interface", runner)
                clock = next(name for name in ("clk", "i_clk", "S_AXI_ACLK", "M_AXIS_ACLK") if name in ports)
                table = next(t["table"] for t in meta["testbenches"] if not t.get("bugs") or bug["name"] in t["bugs"])
                base = encode_table(original / table, ports, clock, folder / "stimulus.hex", folder / "expected.hex")
                base.update({"stimulus": str(folder / "stimulus.hex"), "expected": str(folder / "expected.hex"), "label": "published_discovery_trace"})
                base["independent_oracle_guard"] = verify_frame_length_oracle(base, ports)
                fixed_commands = compile_candidate(fixed, deps, ports, clock, top, folder / "fixed", runner)
                if len(fixed_commands) != 2 or fixed_commands[-1]["status"] != "PASS":
                    raise ValueError("Corrected control failed compilation")
                control = run_trace(folder / "fixed", base, top, runner)
                record["corrected_control"] = control
                if not control["passed"]:
                    raise ValueError("Corrected control disagrees with published trace")
                buggy_commands = compile_candidate(source, deps, ports, clock, top, folder / "buggy", runner)
                if len(buggy_commands) != 2 or buggy_commands[-1]["status"] != "PASS":
                    raise ValueError("Buggy source failed compilation; not a reproduced behavior defect")
                baseline = run_trace(folder / "buggy", base, top, runner)
                record["baseline"] = baseline
                if baseline["passed"] or baseline["command"]["status"] != "PASS":
                    raise ValueError("Public behavioral failure did not reproduce")
                audits = []
                for seed in (7403, 9601):
                    trace = transformed_trace(base, folder / f"audit_{seed}", ports, seed)
                    captured = run_trace(folder / "fixed", trace, top, runner, capture=True)
                    if not captured["passed"]:
                        raise ValueError("Audit capture failed")
                    shutil.copyfile(folder / "fixed/observed.hex", trace["expected"])
                    qualify_expected_file(trace["expected"], trace["outputs"])
                    trace["independent_oracle_guard"] = verify_frame_length_oracle(trace, ports)
                    verify = run_trace(folder / "fixed", trace, top, runner)
                    if not verify["passed"]:
                        raise ValueError("Audit control did not reproduce captured expected values")
                    audits.append(trace)
                case_data = DATA / case_id
                case_data.mkdir(exist_ok=True)
                (case_data / "input.v").write_text(source)
                (case_data / "dependencies.v").write_text(deps)
                (CONTROLS / (case_id + ".v")).write_text(fixed)
                all_traces = [base] + audits
                trace_data = []
                for i, trace in enumerate(all_traces):
                    dest = case_data / f"trace_{i}"
                    dest.mkdir(exist_ok=True)
                    for label in ("stimulus", "expected"):
                        shutil.copyfile(trace[label], dest / (label + ".hex"))
                    trace_data.append({**{k: v for k, v in trace.items() if k not in ("stimulus", "expected")},
                                       "stimulus": f"trace_{i}/stimulus.hex", "expected": f"trace_{i}/expected.hex"})
                case = {"id": case_id, "top": top, "clock": clock, "ports": ports, "traces": trace_data,
                        "input_sha256": sha256(source.encode()), "dependencies_sha256": sha256(deps.encode()),
                        "edited_module": next(name for name in ("axis_adapter", "axis_async_fifo", "axis_fifo", "axis_frame_fifo", "axis_frame_len", "axis_switch", "llsdspi", "sdspi") if ("module " + name) in source.replace("\t", " ")),
                        "license": "GPL-3.0-or-later" if project.startswith("zipcpu") else "MIT",
                        "kind": "historical_defect", "corrected_source_for_scoring": False,
                        "regression_oracle_uses_corrected_trace_values": True,
                        "oracle_scope": "V2: valid-qualified published outputs and corrected-control audit traces within declared input domain; debug ignored; frame-length expectations independently checked. Not an unbounded/reference-free proof."}
                write_json(case_data / "case.json", case)
                record.update({"qualified": True, "case_data": str(case_data), "trace_cycles": base["cycles"], "top": top})
            except (ValueError, RuntimeError, OSError, KeyError, StopIteration) as exc:
                record["reason"] = str(exc)
            rows.append(record)
            write_json(folder / "qualification.json", record)
            write_json(root / "progress.json", rows)
            print({"id": case_id, "qualified": record["qualified"], "reason": record["reason"], "baseline_mismatches": record.get("baseline", {}).get("mismatch_count")}, flush=True)
    report = {"qualified_cases": [r["id"] for r in rows if r["qualified"]], "cases": rows,
              "exclusions_before_inference": {"axi-lite-s1": "Xilinx-generated source: distribution license unclear", "axi-stream-s2": "Xilinx-generated source: distribution license unclear", "axis-fifo-d4": "Same frame-full defect already used in earlier development; avoid counting it as new", "fadd-d7": "No project descriptor/license qualification in this selected artifact"},
              "new_api_calls": 0, "tools": {name: runner.version(name) for name in ("yosys", "verilator")}}
    write_json(root / "qualification.json", report)
    print(json.dumps({"qualified_cases": report["qualified_cases"], "directory": str(root)}, indent=2))


if __name__ == "__main__":
    main()
