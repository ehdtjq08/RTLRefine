"""Fixed tool commands, bounded processes, and an explicit isolation boundary."""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

from .common import write_json
from .benchmarks import get_benchmark
from .tool_paths import find_tool


class ToolRunner:
    def __init__(self, *, trusted_local: bool = False, timeout: float = 120):
        self.trusted_local = trusted_local
        self.timeout = timeout
        self.deadline: float | None = None

    @property
    def mode(self) -> str:
        return "trusted_local_no_isolation" if self.trusted_local else "bubblewrap"

    @staticmethod
    def environment() -> dict[str, str]:
        # Provider credentials and the caller's HOME are never inherited.
        paths = [str(Path(p).parent) for p in
                 (find_tool("yosys"), find_tool("iverilog"),
                  find_tool("vvp"), find_tool("verilator")) if p]
        return {"PATH": ":".join(dict.fromkeys(paths + ["/usr/bin", "/bin"])),
                "LANG": "C", "LC_ALL": "C", "HOME": "/nonexistent"}

    @staticmethod
    def version(name: str) -> str | None:
        executable = find_tool(name)
        if not executable:
            return None
        flag = "--version" if name in ("verilator", "prlimit", "bwrap") else "-V"
        try:
            value = subprocess.run([executable, flag], capture_output=True,
                                   text=True, timeout=5, env=ToolRunner.environment())
            line = (value.stdout + value.stderr).strip().splitlines()[0]
            if name == "yosys":
                match = re.match(r"(Yosys \S+) \(git sha1 ([0-9a-f]+)", line)
                if match:
                    return f"{match[1]} (git sha1 {match[2]})"
            return line[:1024]
        except (OSError, subprocess.TimeoutExpired, IndexError):
            return "version unavailable"

    def sandbox_command(self, command: list[str], cwd: Path) -> list[str]:
        bwrap = find_tool("bwrap")
        if not bwrap:
            raise RuntimeError("bubblewrap is unavailable; generated RTL will not be executed")
        args = [bwrap, "--unshare-all", "--die-with-parent", "--new-session",
                "--cap-drop", "ALL", "--clearenv"]
        for location in ("/usr", "/bin", "/lib", "/lib64", "/etc/ld.so.cache"):
            if Path(location).exists():
                args += ["--ro-bind", location, location]
        # Conda tools need their installation prefix, not the user's home.
        prefixes = set()
        for name in ("yosys", "iverilog", "vvp", "verilator"):
            executable = find_tool(name)
            if executable and not executable.startswith(("/usr/", "/bin/")):
                prefixes.add(str(Path(executable).parent.parent))
        for prefix in sorted(prefixes):
            if prefix in ("/", str(Path.home()), "/home", "/tmp"):
                raise RuntimeError("Refusing an overly broad tool-prefix mount")
            args += ["--ro-bind", prefix, prefix]
        args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                 "--bind", str(cwd.resolve()), "/work", "--chdir", "/work"]
        for key, value in self.environment().items():
            args += ["--setenv", key, value]
        args += ["--setenv", "TMPDIR", "/tmp", "--"] + command
        return args

    def probe(self, directory: Path) -> tuple[bool, str]:
        if self.trusted_local:
            return True, "Trusted, developer-authored RTL only; OS isolation is disabled."
        directory.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(self.sandbox_command(["/bin/true"], directory),
                                    env=self.environment(), capture_output=True,
                                    text=True, timeout=5, start_new_session=True)
            if result.returncode:
                return False, (result.stderr or result.stdout).strip()[:1000]
            return True, "Network and filesystem namespaces available."
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            return False, str(exc)

    def run(self, kind: str, cwd: Path, top: str = "adder_tree") -> dict:
        top = get_benchmark(top).name
        # Callers choose a stage, never a shell command or executable argument.
        commands = {
            "inspect": ["yosys", "-Q", "-T", "-s", "inspect.ys"],
            "equivalence": ["yosys", "-Q", "-T", "-s", "equivalence.ys"],
            "synthesis": ["yosys", "-Q", "-T", "-s", "synth.ys"],
            "lint_iverilog": ["iverilog", "-g2012", "-Wall", "-s", top, "-t", "null", "candidate.v"],
            "lint_verilator": ["verilator", "--lint-only", "--top-module", top, "-Wall", "-Wno-DECLFILENAME", "-Wno-UNUSED", "candidate.v"],
            "compile_simulation": ["iverilog", "-g2012", "-Wall", "-s", "tb", "-o", "simulation.vvp", "candidate.v", "tb.v"],
            "simulate": ["vvp", "simulation.vvp"],
        }
        if kind not in commands:
            raise ValueError("Unknown tool stage")
        command = commands[kind].copy()
        path = find_tool(command[0])
        log_path = cwd / f"{kind}.log"
        started = time.monotonic()
        record = {"stage": kind, "status": "ERROR", "returncode": None,
                  "elapsed_seconds": 0.0, "log": log_path.name,
                  "execution_mode": self.mode, "command": command}
        if not path:
            log_path.write_text(f"Required executable not found: {command[0]}\n")
        else:
            command[0] = path
            timeout = self.timeout
            if self.deadline is not None:
                timeout = min(timeout, self.deadline - time.monotonic())
            if timeout <= 0:
                record["status"] = "TIMEOUT"
                log_path.write_text("Run time budget exhausted before stage\n")
            else:
                process = None
                try:
                    if not self.trusted_local:
                        command = self.sandbox_command(command, cwd)
                    limiter = find_tool("prlimit")
                    if not limiter:
                        raise RuntimeError("util-linux prlimit is required for resource-limited workers")
                    # No preexec_fn: this launcher is also safe to call from a
                    # Streamlit worker thread. Limits survive exec into the tool.
                    command = [limiter, "--core=0", "--as=2147483648", "--fsize=33554432",
                               "--nofile=128", "--cpu=120:121", "--"] + command
                    env = self.environment()
                    env["TMPDIR"] = str(cwd.resolve() / "tmp") if self.trusted_local else "/tmp"
                    (cwd / "tmp").mkdir(exist_ok=True)
                    with log_path.open("wb") as log:
                        process = subprocess.Popen(command, cwd=cwd, env=env,
                                                   stdin=subprocess.DEVNULL,
                                                   stdout=log, stderr=subprocess.STDOUT,
                                                   start_new_session=True)
                        record["returncode"] = process.wait(timeout=timeout)
                    record["status"] = ("PASS" if record["returncode"] == 0 else
                                        "ERROR" if record["returncode"] < 0 else "FAIL")
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    record["returncode"] = process.returncode
                    record["status"] = "TIMEOUT"
                except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                    log_path.write_text(str(exc) + "\n")
        record["elapsed_seconds"] = round(time.monotonic() - started, 6)
        write_json(cwd / f"{kind}.command.json", record)
        return record
