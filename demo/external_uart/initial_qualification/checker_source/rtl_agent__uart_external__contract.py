"""Pinned UART interface and behavioral contract, never corrected RTL."""
from __future__ import annotations

import json
import re

from ..common import ROOT

DATA = ROOT / "external_cases/wbuart32_cts"
VENDOR = ROOT / "third_party/wbuart32_cts"
# The second group is not sent to the model and never controls a retry.
DISCOVERY = ((4, 8, "none", 1, 1103), (6, 7, "mark", 2, 2207), (5, 5, "space", 1, 3301))
AUDIT = ((7, 6, "mark", 2, 7403), (11, 8, "none", 2, 8501), (9, 7, "space", 1, 9601))
FORMAL = ((4, 80), (5, 96))


def specification():
    return json.loads((DATA / "contract.json").read_text())


def split_source(source):
    marker = "\twire\t[27:0]\tclocks_per_baud, break_condition;"
    if source.count(marker) != 1 or source.count("`ifdef\tFORMAL") != 1:
        raise ValueError("Unsupported pinned txuart source layout")
    start, end = source.index(marker), source.index("`ifdef\tFORMAL")
    return source[:start], source[start:end], source[end:]


def source_policy(source):
    if not isinstance(source, str) or not 1 <= len(source.encode()) <= 65000:
        raise ValueError("UART source must be at most 65 KB")
    prefix, body, suffix = split_source(source)
    if prefix != (DATA / "interface.vh").read_text() or suffix != (DATA / "upstream_formal_suffix.vh").read_text():
        raise ValueError("Preserve upstream license, public interface and disabled upstream formal appendix")
    clean = re.sub(r"/\*.*?\*/|//[^\n]*", " ", body, flags=re.S)
    if any(token in clean for token in ("$", "`", '"', "\\", "(*", "*)", "#")):
        raise ValueError("No tasks, directives, strings, attributes or delays in production edits")
    if re.search(r"translate_off|translate_on|synopsys|pragma", body, re.I):
        raise ValueError("No compiler comment directives")
    if re.search(r"\b(module|endmodule|task|function|force|release|bind|import|export|specify|forever|while|repeat|wait|assert|assume|cover|restrict|tb|property_top)\b", clean):
        raise ValueError("No added modules, behavioral tasks, properties or checker access")
    if re.search(r"\b\w+\s*\.\s*\w+", clean):
        raise ValueError("No hierarchical access")
    if re.search(r"\bi_(?:clk|reset|setup|break|wr|data|cts_n)\s*(?:\[[^\]]+\])?\s*(?:<=|=(?!=))", clean):
        raise ValueError("Do not drive input ports")
    if re.findall(r"\binitial\s+([^;]+);", clean) != specification()["allowed_initial_assignments"]:
        raise ValueError("Preserve existing production initial assignments; do not add any")
    # State case patterns already use '?'; actual value assignments may not use X/Z.
    for match in re.finditer(r"(?:<=|=(?!=))\s*([^;]+);", clean):
        if re.search(r"'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]*[xXzZ?]", match.group(1)):
            raise ValueError("No unknown literal assignments")
    events = re.findall(r"\balways\s*@\s*\(([^)]*)\)", clean)
    if any(re.sub(r"\s+", "", event) != "posedgei_clk" for event in events):
        raise ValueError("Keep production logic synchronous to the public clock")
    return source
