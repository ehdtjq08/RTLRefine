"""Fixed isolated EDA commands; reuse the existing filesystem/network boundary."""
from __future__ import annotations

import os
import signal
import subprocess
import time

from ..common import write_json
from ..tool_paths import find_tool
from ..tool_runner import ToolRunner


class SequentialRunner(ToolRunner):
    def run(self, kind, cwd, top=None):
        commands = {
            "compile_simulation": ["iverilog", "-g2012", "-Wall", "-s", "tb", "-o", "simulation.vvp", "candidate.v", "tb.v"],
            "simulate": ["vvp", "simulation.vvp"],
            "bounded": ["yosys", "-Q", "-T", "-s", "bounded.ys"],
        }
        if kind not in commands:
            raise ValueError("Unknown sequential EDA profile")
        argv = commands[kind].copy()
        record = {"stage": kind, "status": "ERROR", "command": argv.copy(),
                  "execution_mode": self.mode, "returncode": None}
        log = cwd / (kind + ".log")
        start = time.monotonic()
        process = None
        try:
            tool, limiter = find_tool(argv[0]), find_tool("prlimit")
            if not tool or not limiter:
                raise RuntimeError("Required EDA tool is unavailable")
            argv[0] = tool
            if not self.trusted_local:
                argv = self.sandbox_command(argv, cwd)
            argv = [limiter, "--core=0", "--as=2147483648", "--fsize=33554432", "--nofile=128", "--cpu=120:121", "--", *argv]
            with log.open("wb") as stream:
                process = subprocess.Popen(argv, cwd=cwd, env=self.environment(), stdin=subprocess.DEVNULL,
                                           stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                record["returncode"] = process.wait(timeout=self.timeout)
            record["status"] = "PASS" if record["returncode"] == 0 else "FAIL"
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            record["status"] = "TIMEOUT"
        except (RuntimeError, OSError) as exc:
            log.write_text(str(exc) + "\n")
        record["elapsed_seconds"] = round(time.monotonic() - start, 6)
        write_json(cwd / (kind + ".command.json"), record)
        return record
