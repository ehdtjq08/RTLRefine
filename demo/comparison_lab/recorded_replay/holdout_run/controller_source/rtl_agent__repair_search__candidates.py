"""Finite source-edit grammar for a separate development ablation.

This is restricted lexical generation with Yosys-resolved widths, not a general
Verilog AST or an SMT solver. No corrected source or test outcome is an input.
"""
from __future__ import annotations

from collections import defaultdict
import itertools
import re

from ..common import sha256
from .retention import candidates as retention_candidates, comment_blanked

FAMILIES = ("state_retention", "reset_completion", "reported_value_reset", "handshake_reset_gate",
            "condition_gate", "index_stride", "ack_pipeline", "word_byte_order")
MAX_POOL = 128
FAMILY_CAP = 32


def closing(text, start, left="(", right=")"):
    depth = 0
    for i in range(start, len(text)):
        if text[i] == left:
            depth += 1
        elif text[i] == right:
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("Unbalanced supported source construct")


def end_block(text, begin):
    depth = 0
    for match in re.finditer(r"\b(?:begin|end)\b", text[begin:]):
        depth += 1 if match.group() == "begin" else -1
        if depth == 0:
            return begin + match.start(), begin + match.end()
    raise ValueError("Unbalanced supported begin/end block")


def make_pool(source, widths):
    clean = comment_blanked(source)
    editable = source.index(");") + 2
    families = defaultdict(list)
    seen = set()

    def add(family, edits, note):
        edits = sorted(edits)
        if not edits or any(a[1] > b[0] for a, b in zip(edits, edits[1:])):
            return
        if any(start < editable for start, _, _ in edits):
            return
        candidate = source
        for start, end, replacement in reversed(edits):
            candidate = candidate[:start] + replacement + candidate[end:]
        digest = sha256(candidate.encode())
        if digest in seen or candidate == source:
            return
        seen.add(digest)
        families[family].append({"family": family, "line": source.count("\n", 0, edits[0][0]) + 1,
            "note": note, "edits": [{"start": a, "end": b, "old": source[a:b], "replacement": t} for a,b,t in edits],
            "changed_spans": len(edits), "rtl_sha256": digest, "rtl": candidate})

    # Persistent combinational defaults. Pulse flags remain alternatives which
    # the executable checks must distinguish from persistent state.
    for option in retention_candidates(source):
        candidate = option["rtl"]
        # The retention prototype edits one literal span; recover that exact span.
        i = next(i for i,(a,b) in enumerate(zip(source,candidate)) if a != b)
        old_end = i + len(option["old"])
        add("state_retention", [(i, old_end, option["replacement"])], "Retain existing " + option["state"] + " state instead of a constant default")

    # Complete an explicit synchronous reset using other registers assigned by
    # the SAME always block. Arrays are not initialized by this grammar.
    arrays = set(re.findall(r"\b(?:reg|wire)\s*(?:\[[^\]]+\]\s*)?(\w+)\s*\[", clean))
    for event in re.finditer(r"\balways\s*@\s*\([^)]*\)\s*begin\b", clean):
        if "posedge" not in event.group() and "negedge" not in event.group():
            continue
        begin = clean.rfind("begin", event.start(), event.end())
        block_end, _ = end_block(clean, begin)
        fragment = clean[event.end():block_end]
        for reset in re.finditer(r"\bif\s*\(([^()]*)\)\s*begin\b", fragment):
            if not re.search(r"rst|reset", reset.group(1), re.I):
                continue
            reset_begin = event.end() + fragment.rfind("begin", reset.start(), reset.end())
            reset_end, reset_after = end_block(clean, reset_begin)
            assigned = set(re.findall(r"\b(\w+)\s*<=", clean[event.end():block_end]))
            initialized = set(re.findall(r"\b(\w+)\s*<=", clean[reset_begin:reset_end]))
            missing = sorted(assigned - initialized - arrays)
            choices = [[name] for name in missing]
            if 1 < len(missing) <= 3:
                choices.append(missing)
            for names in choices:
                text = "\n" + "\n".join(f"        {name} <= 0;" for name in names) + "\n    "
                add("reset_completion", [(reset_end, reset_end, text)], "Reset same-block state: " + ", ".join(names))
            break

    # A reported accumulator may need clearing after its validity pulse. This
    # is based on matching signal names, not a benchmark/case-name exception.
    for block in re.finditer(r"\balways\s*@\s*(?:\*|\(\s*\*\s*\))\s*begin\b", clean):
        tail = clean[block.end():]
        boundary = re.search(r"\b(?:if|case|casez|casex|for|while|begin|end)\b", tail)
        if not boundary:
            continue
        prefix = tail[:boundary.start()]
        for match in re.finditer(r"\b(\w+)_next\s*=\s*\1_reg\s*;", prefix):
            name = match.group(1)
            flag = name + "_valid_reg"
            if flag not in widths or widths[flag] != 1 or widths.get(name + "_reg", 1) == 1:
                continue
            point = block.end() + boundary.start()
            add("reported_value_reset", [(point, point, f"if ({flag}) {name}_next = 0;\n    ")], "Clear reported " + name + " after its valid pulse")

    scalar = {name for name,width in widths.items() if width == 1 and not re.search(r"(?:^|_)(?:clk|clock)(?:_|$)", name)}
    resets = sorted((name for name in scalar if re.search(r"rst|reset", name, re.I)))
    for assign in re.finditer(r"\bassign\s+(\w+)\s*=\s*([^;]+);", clean):
        name, expr = assign.group(1), assign.group(2)
        if not re.search(r"ready$", name):
            continue
        # Domain-prefix matches precede other reset signals, independent of tests.
        reset_order = sorted(resets, key=lambda s: (not s.startswith(name.split("_")[0]), s))[:8]
        for reset in reset_order:
            if re.search(r"\b" + re.escape(reset) + r"\b", expr):
                continue
            for term in ("!" + reset, reset):
                add("handshake_reset_gate", [(assign.start(2), assign.end(2), f"({expr.strip()}) && ({term})")], "Qualify readiness with " + term)

    # Qualify conditions using scalar signals mentioned in nearby conditions.
    conditions = []
    for match in re.finditer(r"\bif\s*\(", clean):
        start = clean.index("(", match.start(), match.end())
        end = closing(clean, start)
        if start >= editable:
            conditions.append((start + 1, end, clean[start + 1:end]))
    for i,(start,end,condition) in enumerate(conditions):
        nearby = []
        for j in sorted(range(len(conditions)), key=lambda j: (abs(j-i), j)):
            if j == i or abs(j-i) > 2:
                continue
            for name in re.findall(r"\b[A-Za-z_]\w*\b", conditions[j][2]):
                if name in scalar and name not in nearby and not re.search(r"\b"+re.escape(name)+r"\b", condition):
                    nearby.append(name)
        for name in nearby[:4]:
            for term in (name, "!" + name):
                add("condition_gate", [(start,end,f"({source[start:end]}) && ({term})")], "Qualify condition with nearby scalar " + term)

    # Matrix-index strides may use the other public cardinality parameter.
    counts = sorted(set(re.findall(r"\bparameter\s+(?:integer\s+)?([A-Za-z_]\w*_COUNT)\s*=", clean)))
    index_edits = []
    for index in re.finditer(r"\[([^\[\]\n]+)\]", clean[editable:]):
        expression = index.group(1)
        if ":" in expression:
            continue
        for product in re.finditer(r"\b\w+\s*\*\s*(\w+_COUNT)\b", expression):
            old = product.group(1)
            if old not in counts:
                continue
            start = editable + index.start(1) + product.start(1)
            end = editable + index.start(1) + product.end(1)
            for other in counts:
                if other == old:
                    continue
                edit = (start,end,other)
                index_edits.append(edit)
                add("index_stride", [edit], f"Use {other} instead of {old} in matrix index")
    for a,b in list(itertools.combinations(index_edits,2))[:16]:
        if a[0] != b[0]:
            add("index_stride", [a,b], "Coordinate two matrix-index stride substitutions")

    # Wishbone-style ack/strobe/cycle names imply a closed acknowledgment grammar.
    for match in re.finditer(r"always\s*@\s*\(\s*posedge\s+(\w+)\s*\)\s*(\w+_ack)\s*<=\s*(\w+_stb)\s*;", clean):
        clk, ack, stb = match.groups()
        cycle_options = sorted(name for name in scalar if name.endswith("_cyc"))
        for cycle in cycle_options[:2]:
            gate = f"always @(posedge {clk}) {ack} <= ({cycle}) && ({stb});"
            add("ack_pipeline", [(match.start(),match.end(),gate)], "Qualify acknowledgment with active bus cycle")
            temp = "__rtlrefine_ack_delay"
            if re.search(r"\b"+temp+r"\b", clean):
                continue
            initial = "" if re.search(r"\binitial\s+"+re.escape(ack)+r"\s*=", clean) else f"initial {ack}=0;\n"
            pipeline = f'''reg {temp}=0;
{initial}always @(posedge {clk}) begin
 if (!{cycle}) begin {temp}<=0; {ack}<=0; end
 else begin {temp}<={stb}; {ack}<={temp}; end
end'''
            add("ack_pipeline", [(match.start(),match.end(),pipeline)], "One-cycle acknowledgment pipeline qualified by active bus cycle")

    # Reverse 32-bit word byte order, independently or in similarly named lanes.
    packing = defaultdict(list)
    for match in re.finditer(r"\b(\w+)\s*<=\s*(\w+)\s*;", clean):
        lhs,rhs = match.groups()
        if widths.get(lhs) != 32 or widths.get(rhs) != 32:
            continue
        swap = "{" + ",".join(f"{rhs}[{i+7}:{i}]" for i in (0,8,16,24)) + "}"
        edit = (match.start(2),match.end(2),swap)
        add("word_byte_order", [edit], "Reverse bytes feeding " + lhs)
        stem = re.sub(r"_(?:a|b|\d+)_", "_lane_", lhs)
        packing[(stem,rhs)].append(edit)
    for (_,rhs),edits in packing.items():
        if 1 < len(edits) <= 4:
            add("word_byte_order", edits, "Coordinate byte reversal across similarly named lanes fed by " + rhs)

    # Fair deterministic pool truncation: round-robin families, source order
    # within each family. Both methods receive exactly this same pool.
    pool = []
    for i in range(FAMILY_CAP):
        for family in FAMILIES:
            if i < len(families[family]):
                pool.append(families[family][i])
                if len(pool) == MAX_POOL:
                    break
        if len(pool) == MAX_POOL:
            break
    for i,item in enumerate(pool,1):
        item["id"] = f"candidate_{i:03d}"
    return pool
