"""Public queue specification and candidate boundary; no clean RTL is loaded."""
import json
import re

from ..common import ROOT

DATA = ROOT / "mutation_cases/stream_buffer"
DISCOVERY = ((2, 1103, 240), (1, 2207, 256), (2, 3301, 272))
AUDIT = ((3, 7403, 480), (2, 8501, 512), (3, 9601, 544))
FORMAL_PROFILES = ((1, 16), (2, 12))


def specification():
    return json.loads((DATA / "contract.json").read_text())


def source_policy(source):
    if not isinstance(source, str) or not 1 <= len(source.encode()) <= 16000:
        raise ValueError("Use a UTF-8 Verilog module of at most 16 KB")
    if not source.startswith("// SPDX-License-Identifier: MIT\n"):
        raise ValueError("Preserve the MIT SPDX notice")
    if re.search(r"translate_off|translate_on|synopsys|pragma", source, re.I):
        raise ValueError("Compiler comment directives are unsupported")
    clean = re.sub(r"/\*.*?\*/|//[^\n]*", " ", source, flags=re.S)
    interface = re.sub(r"/\*.*?\*/|//[^\n]*", " ", (DATA / "interface.vh").read_text(), flags=re.S)
    if ");" not in clean or re.sub(r"\s+", "", clean[:clean.index(");") + 2]) != re.sub(r"\s+", "", interface):
        raise ValueError("Keep the public module parameters and ports unchanged; whitespace may vary")
    if any(token in clean for token in ("$", "`", '"', "\\", "(*", "*)")):
        raise ValueError("System tasks, macros, strings, escaped names and attributes are unsupported")
    if re.search(r"\b(initial|final|task|function|force|release|bind|import|export|specify|forever|while|repeat|wait|assert|assume|cover|restrict|tb|property_top|spec_queue|checker)\b", clean):
        raise ValueError("Behavioral tasks, properties, assumptions and checker access are unsupported")
    if re.findall(r"\bmodule\s+(\w+)", clean) != ["stream_buffer"] or len(re.findall(r"\bendmodule\b", clean)) != 1:
        raise ValueError("Exactly the supported stream_buffer module is required")
    body = clean[clean.index(");") + 2:]
    if re.search(r"\b(?:clk|rst|s_data|s_valid|s_last|s_user|m_ready)\s*(?:\[[^\]]+\])?\s*(?:<=|=(?!=))", body):
        raise ValueError("Candidate logic must not drive its input ports")
    if "#" in body or re.search(r"\b\w+\s*\.\s*\w+", body):
        raise ValueError("Timing delays and hierarchical access are unsupported")
    if re.search(r"'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]*[xXzZ?]", body):
        raise ValueError("Unknown literals are unsupported")
    return source
