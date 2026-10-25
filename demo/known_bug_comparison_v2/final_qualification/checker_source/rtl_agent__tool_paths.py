"""Prefer the project-local Verilator without changing the caller's PATH."""
import os
import shutil

from .common import ROOT


def find_tool(name: str) -> str | None:
    if name == "verilator":
        local = ROOT / ".tools/bin/verilator"
        if local.is_file() and os.access(local, os.X_OK):
            return str(local)
    return shutil.which(name)
