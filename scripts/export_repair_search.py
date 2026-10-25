"""Export complete constrained-search records, retaining failures and rankings."""
import json
from pathlib import Path
import shutil

from rtl_agent.common import ROOT,sha256,write_json


def ignore(path,names):
    return [n for n in names if n in ("obj_dir","__pycache__") or n.endswith((".pyc",".o",".a",".vvp"))
            or (Path(path).name=="compiled" and n in ("stimulus.hex","expected.hex"))]


def main():
    run=ROOT/"results/repair_search_comparison_v1_20261023";result=json.loads((run/"summary.json").read_text())
    if result["status"]!="COMPLETE":raise ValueError("Do not export partial search results as complete")
    out=ROOT/"demo/repair_search";out.mkdir(exist_ok=False)
    shutil.copytree(run,out/"run",ignore=ignore)
    shutil.copytree(ROOT/"results/repair_search_pools_v1_20261023",out/"prepared_pools",ignore=ignore)
    (out/"MODIFICATIONS.md").write_text('''# Constrained repair source attribution

Original Verilog-axis source retains Alex Forencich's MIT notices. ZipCPU SPI
source and generated derivatives retain Gisselquist Technology's GPL-3.0-or-later
license. Complete original/modified source, dependencies and applicable licenses
accompany the evidence. Research artifact portions retain BSD attribution.
The root MIT project license does not replace vendor licensing.

On 2026-10-23 the project-authored restricted edit grammar generated every
candidate before model ranking. NVIDIA Nemotron on Nebius only ranked existing
IDs; it did not write the source. No functional manual repair was made.
Each method had at most eight discovery candidate evaluations, a common first
two and the same pool. Selected sources were audited only after both selections
were fixed. A failed audit never granted another candidate. This is a known
development cohort following V2 and a retention pilot, not new/held-out accuracy,
unbounded correctness, an SMT implementation or proof of algorithmic novelty.
''')
    shutil.copyfile(ROOT/"research/known_bug_benchmark/ARTIFACT-LICENSE-BSD-3-Clause.txt",out/"ARTIFACT-LICENSE-BSD-3-Clause.txt")
    write_json(out/"manifest.json",{str(p.relative_to(out)):sha256(p.read_bytes()) for p in sorted(out.rglob('*')) if p.is_file()})
    print(json.dumps({k:result[k] for k in ('status','totals','paired_real_outcomes','unique_model_calls','estimated_api_cost_usd')},indent=2))


if __name__=='__main__':main()
