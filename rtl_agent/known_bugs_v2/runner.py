"""Closed EDA/native-run commands inside the existing namespace boundary."""
from __future__ import annotations

import os
import re
import signal
import subprocess
import time

from ..common import write_json
from ..tool_paths import find_tool
from ..tool_runner import ToolRunner


class BenchmarkRunner(ToolRunner):
    def __init__(self):
        super().__init__(timeout=120)

    def run(self, stage, directory, top, *, capture=False):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", top):
            raise ValueError("Invalid pinned module name")
        commands = {
            "inspect": ["yosys", "-Q", "-T", "-s", "inspect.ys"],
            "translate": ["verilator", "--cc", "--exe", "-Wno-fatal", "--x-initial", "0", "--x-assign", "0",
                          "--top-module", top, "--Mdir", "obj_dir", "candidate.v", "dependencies.v", "harness.cpp"],
            "build": ["make", "-C", "obj_dir", "-f", "V" + top + ".mk", "-j1", "OPT_FAST=-O0", "OPT_SLOW=-O0"],
            "simulate": ["./obj_dir/V" + top] + (["capture"] if capture else []),
        }
        if stage not in commands:
            raise ValueError("Unsupported public-benchmark command")
        command = commands[stage].copy()
        record = {"stage": stage, "command": command, "status": "ERROR", "returncode": None,
                  "execution_mode": "bubblewrap", "zero_initialization": True}
        log = directory / (stage + ".log")
        started, process = time.monotonic(), None
        try:
            limiter = find_tool("prlimit")
            if not limiter:
                raise RuntimeError("prlimit required")
            if stage != "simulate":
                command[0] = find_tool(command[0])
                if not command[0]:
                    raise RuntimeError("Missing benchmark compiler/tool")
            command = self.sandbox_command(command, directory)
            command = [limiter, "--core=0", "--as=2147483648", "--fsize=33554432", "--nofile=128", "--cpu=120:121", "--", *command]
            with log.open("wb") as output:
                process = subprocess.Popen(command, cwd=directory, env=self.environment(), stdin=subprocess.DEVNULL,
                                           stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                record["returncode"] = process.wait(timeout=self.timeout)
            record["status"] = "PASS" if record["returncode"] == 0 else "FAIL"
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            record["status"] = "TIMEOUT"
        except (RuntimeError, OSError) as exc:
            log.write_text(str(exc) + "\n")
        record["elapsed_seconds"] = round(time.monotonic() - started, 4)
        write_json(directory / (stage + ".command.json"), record)
        return record
