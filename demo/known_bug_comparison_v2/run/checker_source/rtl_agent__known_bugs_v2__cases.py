"""Source boundary and immutable descriptors for qualified public regressions."""
from __future__ import annotations

import json
import re

from ..common import ROOT

DATA = ROOT / "external_cases/known_bugs_v2"


def load(case_id):
    if not re.fullmatch(r"[a-z0-9_-]+", case_id):
        raise ValueError("Invalid known-bug case identifier")
    path = DATA / case_id / "case.json"
    return json.loads(path.read_text())


def canonical(source):
    return re.sub(r"\s+", "", re.sub(r"/\*.*?\*/|//[^\n]*", " ", source, flags=re.S))


def code_only(source):
    # Preserve line numbers while hiding comments, including artifact labels and
    # old filename/location hints. License is retained in executed/downloaded RTL.
    return re.sub(r"/\*.*?\*/|//[^\n]*", lambda m: "\n" * m.group().count("\n"), source, flags=re.S)


def source_policy(source, original, ports):
    if not isinstance(source, str) or not 1 <= len(source.encode()) <= 90000:
        raise ValueError("Use a single supported source file <=90 KB")
    clean, old = code_only(source), code_only(original)
    if ");" not in source or source[:source.index(");") + 2] != original[:original.index(");") + 2]:
        raise ValueError("Preserve the original license/interface prefix exactly")
    for pattern in (r"\b(?:input|output|inout)\b[^;]+;", r"\bparameter\b[^;]+;", r"`[^\n]*"):
        if [canonical(v) for v in re.findall(pattern, clean)] != [canonical(v) for v in re.findall(pattern, old)]:
            raise ValueError("Do not change public ports, configuration parameters or compiler directives")
    if re.findall(r"\bmodule\s+(\w+)", clean) != re.findall(r"\bmodule\s+(\w+)", old) or clean.count("endmodule") != old.count("endmodule"):
        raise ValueError("Keep module boundaries unchanged")
    if re.search(r"\b(force|release|bind|import|export|task|function|specify|forever|while|repeat|wait|assert|assume|cover|restrict|property_top|harness|Verilated)\b", clean):
        raise ValueError("Unsupported behavioral code or checker access")
    if re.search(r"\b\w+\s*\.\s*\w+", clean):
        raise ValueError("No hierarchical checker or dependency access")
    if any(name not in ("$clog2", "$bits") for name in re.findall(r"\$\w+", clean)):
        raise ValueError("No runtime system tasks or file access")
    for name, port in ports.items():
        if port["direction"] == "input" and re.search(r"\b" + re.escape(name) + r"\s*(?:\[[^\]]+\])?\s*(?:<=|=(?!=))", clean):
            raise ValueError("Do not drive public input ports")
    for comment in re.findall(r"/\*.*?\*/|//[^\n]*", source, re.S):
        if re.search(r"translate_off|translate_on|synopsys|verilator|pragma", comment, re.I) and comment not in original:
            raise ValueError("No new compiler comment directives")
    old_events = {canonical(e) for e in re.findall(r"\balways\s*@\s*\(([^)]*)\)", old)}
    if any(canonical(e) not in old_events for e in re.findall(r"\balways\s*@\s*\(([^)]*)\)", clean)):
        raise ValueError("Use an existing clock/reset or combinational event form")
    body = source[source.index(");") + 2:]
    if re.search(r"#\s*(?!\(\s*\.)(?:\d|[A-Za-z_]|\()", code_only(body)):
        raise ValueError("No timing delays or changed positional parameterization")
    return source


def public_contract(case):
    project = case["id"].split("_")[0]
    descriptions = {
        "axis-adapter-s3": "Ready/valid stream width adapter. Preserve the order of TKEEP-enabled bytes, end-of-frame and user metadata under backpressure; consume source words only on handshakes.",
        "axis-async-fifo-c4": "Dual-clock ready/valid FIFO behind a registered frontend. Respect reset flushing and handshake ownership. This recorded profile uses one clock for both FIFO domains; no CDC/metastability claim.",
        "axis-fifo-d12": "Frame-aware FIFO. Preserve accepted complete frames and metadata; when an overflowing frame must be dropped, do not publish a surviving suffix as a valid frame.",
        "axis-frame-fifo-d11": "Frame FIFO. Reset flushes packet pointers and partial/drop state. Preserve ordering and end-of-frame metadata across stalls and repeated reset.",
        "axis-frame-len-d13": "Frame-length monitor. Supported TKEEP values are contiguous low-order ones (2^k-1, including zero); noncontiguous masks are outside this artifact contract. Count those enabled bytes only on valid AND ready transfers; report each completed frame, including consecutive single-word frames and stalls.",
        "axis-switch-d8": "Parameterized stream switch. Route data/metadata to configured destinations; propagate readiness to the correct source and validity to the correct destination. Source and destination counts can differ.",
        "zipcpu-spi-c1-c3-d9": "Wishbone-controlled SD-card SPI interface. Preserve bus-cycle-qualified acknowledgments, divider/startup timing, serial bit order, FIFO word/byte order and configured behavior. Do not refactor unrelated datapaths.",
    }
    return {"module_role": descriptions.get(project, "Same public RTL contract as this design family"),
            "top": case["top"], "clock": case["clock"], "ports": case["ports"],
            "admission": "Match fixed-configuration cycle-exact public-port regression behavior. This is a trace oracle, not an unbounded property proof. Two additional audit input sequences are unavailable to the model.",
            "execution": "Native Verilator two-state simulation, unspecified initialization zero, explicit Verilog initial values retained",
            "editing": "Only edit the displayed original file; preserve ports, parameters, directives and license/header. Dependencies are read-only."}
