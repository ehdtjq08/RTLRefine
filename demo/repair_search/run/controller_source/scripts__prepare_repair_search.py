"""Prepare the same source-only candidate pools before any ranking request."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rtl_agent.common import ROOT,new_run_dir,sha256,write_json
from rtl_agent.known_bugs_v2.cases import DATA,load,source_policy
from rtl_agent.known_bugs_v2.evaluator import _editable_ports
from rtl_agent.known_bugs_v2.engine import inspect
from rtl_agent.known_bugs_v2.runner import BenchmarkRunner
from rtl_agent.repair_search.candidates import make_pool


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--output",required=True);args=parser.parse_args()
    root=new_run_dir("repair_search_pool_preparation",args.output)
    dataset=json.loads((DATA/"dataset.json").read_text());runner=BenchmarkRunner()
    ok,why=runner.probe(root/"isolation")
    if not ok:raise RuntimeError(why)
    rows=[]
    for entry in dataset["cases"]:
        case=load(entry["case_id"]);source=(DATA/case["id"]/"input.v").read_text();deps=(DATA/case["id"]/"dependencies.v").read_text()
        folder=root/entry["opaque_id"];folder.mkdir()
        inspect(source,deps,case["top"],folder/"original_inspection",runner)
        ir=json.loads((folder/"original_inspection/interface.json").read_text())
        modules=[m for name,m in ir["modules"].items() if name==case["edited_module"] or str(m.get("attributes",{}).get("hdlname",""))==case["edited_module"]]
        if not modules:
            modules=[m for m in ir["modules"].values() if str(m.get("attributes",{}).get("src","")).startswith("candidate.v:")]
        if len(modules)!=1:raise ValueError("Ambiguous original editable module")
        widths={name:len(net["bits"]) for name,net in modules[0]["netnames"].items() if not name.startswith("$") and "." not in name}
        pool=make_pool(source,widths)
        retained,rejected=[],[]
        ports=case["ports"] if case["top"]==case["edited_module"] else _editable_ports(source)
        for item in pool:
            try:source_policy(item["rtl"],source,ports);retained.append(item)
            except ValueError as exc:rejected.append({"candidate":{k:v for k,v in item.items() if k!="rtl"},"error":str(exc)})
        # IDs are renumbered after the purely static policy filter, before any simulation/model.
        for i,item in enumerate(retained,1):item["id"]=f"candidate_{i:03d}"
        write_json(folder/"pool.json",retained);write_json(folder/"policy_filtered.json",rejected)
        row={**entry,"candidate_count":len(retained),"families":sorted({p["family"] for p in retained}),"pool_sha256":sha256((folder/"pool.json").read_bytes())}
        rows.append(row);print(row,flush=True)
    files=sorted((ROOT/"rtl_agent/repair_search").glob("*.py"))+[Path(__file__).resolve()]
    hashes={str(p.relative_to(ROOT)):sha256(p.read_bytes()) for p in files}
    write_json(root/"manifest.json",{"cases":rows,"generator_hashes":hashes,"data_seal_sha256":sha256((DATA/"FROZEN.json").read_bytes()),
               "corrected_RTL_used":False,"candidate_simulations_used_to_build_pool":False,"model_calls":0,
               "scope":"Known development cohort after V2 and one retention pilot; not held-out or novel-algorithm evidence"})
    print(json.dumps({"cases":len(rows),"total_candidates":sum(r["candidate_count"] for r in rows)},indent=2))


if __name__=="__main__":main()
