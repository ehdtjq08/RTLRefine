"""Restricted state-retention edit generator; not a general Verilog parser."""
from __future__ import annotations

import re


def comment_blanked(source):
    return re.sub(r"/\*.*?\*/|//[^\n]*", lambda m: re.sub(r"[^\n]", " ", m.group()), source, flags=re.S)


def candidates(source):
    """One edit per literal default, before any control flow in an @* block.

    Candidate order follows source order, with no reference patch, trace result
    or signal-name ranking. Pulse flags and persistent state are both considered;
    the checks must distinguish them. Unsupported syntax is left untouched.
    """
    clean = comment_blanked(source)
    result = []
    for block in re.finditer(r"\balways\s*@\s*(?:\*|\(\s*\*\s*\))\s*begin\b", clean):
        remaining = clean[block.end():]
        boundary = re.search(r"\b(?:if|case|casez|casex|for|while|begin|end)\b", remaining)
        if not boundary:
            continue
        prefix = remaining[:boundary.start()]
        for match in re.finditer(r"\b([A-Za-z_]\w*)_next\s*=\s*(\d+\s*'[bBdDhH][0-9a-fA-F_]+|[01])\s*;", prefix):
            state = match.group(1)
            if not re.search(r"\b" + re.escape(state) + r"_reg\b", clean):
                continue
            start = block.end() + match.start(2)
            end = block.end() + match.end(2)
            replacement = state + "_reg"
            candidate = source[:start] + replacement + source[end:]
            result.append({"index": len(result) + 1, "line": source.count("\n", 0, start) + 1,
                           "kind": "literal_default_to_existing_state", "state": state,
                           "old": source[start:end], "replacement": replacement,
                           "rtl": candidate, "changed_source_spans": 1})
    return result
