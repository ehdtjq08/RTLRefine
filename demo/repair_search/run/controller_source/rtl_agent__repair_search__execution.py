"""Stage discovery separately from passive audit, using the unchanged V2 tools."""
from __future__ import annotations

from pathlib import Path

from ..common import sha256,write_json
from ..known_bugs_v2.cases import DATA,load,source_policy
from ..known_bugs_v2.evaluator import _editable_ports
from ..known_bugs_v2.engine import compile_candidate,run_trace
from ..known_bugs_v2.runner import BenchmarkRunner


def discover(case_id, source, directory):
    case=load(case_id);base=DATA/case_id;directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    original=(base/"input.v").read_text();deps=(base/"dependencies.v").read_text()
    if sha256(original.encode())!=case["input_sha256"] or sha256(deps.encode())!=case["dependencies_sha256"]:
        raise ValueError("Pinned original/dependencies changed")
    (directory/"candidate.v").write_text(source)
    record={"status":"POLICY_REJECTED","discovery_pass":False,"rtl_sha256":sha256(source.encode()),"traces":[],"new_api_calls":0}
    try:
        ports=case["ports"] if case["top"]==case["edited_module"] else _editable_ports(original)
        source_policy(source,original,ports)
        runner=BenchmarkRunner();ok,why=runner.probe(directory/"isolation")
        if not ok:raise RuntimeError(why)
        compiled=directory/"compiled"
        commands=compile_candidate(source,deps,case["ports"],case["clock"],case["top"],compiled,runner)
        record["commands"]=commands
        if len(commands)!=2 or commands[-1]["status"]!="PASS":
            record["status"]="COMPILE_FAILED"
            record["error"]=(compiled/("build.log" if len(commands)==2 else "translate.log")).read_text()[-6000:]
        else:
            item=case["traces"][0];trace={**item,"stimulus":str(base/item["stimulus"]),"expected":str(base/item["expected"])}
            result=run_trace(compiled,trace,case["top"],runner);result["phase"]="discovery"
            record["traces"]=[result];record["discovery_pass"]=result["passed"]
            record["status"]="DISCOVERY_PASS_AUDIT_PENDING" if result["passed"] else "DISCOVERY_TRACE_FAILED"
            (directory/"discovery.log").write_bytes((compiled/"simulate.log").read_bytes())
            if (compiled/"candidate.v").read_text()!=source or (compiled/"dependencies.v").read_text()!=deps:
                raise ValueError("Worker modified source")
    except (ValueError,RuntimeError,OSError,KeyError) as exc:record["error"]=str(exc)
    write_json(directory/"discovery.json",record)
    return {**record,"directory":str(directory)}


def audit(case_id, discovery):
    if not discovery["discovery_pass"]:
        raise ValueError("Only a discovery-selected source may be audited")
    case=load(case_id);base=DATA/case_id;directory=Path(discovery["directory"]);runner=BenchmarkRunner()
    source=(directory/"candidate.v").read_bytes()
    if sha256(source)!=discovery["rtl_sha256"]:raise ValueError("Selected source changed")
    traces=list(discovery["traces"])
    for i,item in enumerate(case["traces"][1:],1):
        trace={**item,"stimulus":str(base/item["stimulus"]),"expected":str(base/item["expected"])}
        result=run_trace(directory/"compiled",trace,case["top"],runner);result["phase"]="unexposed_audit";traces.append(result)
        (directory/f"audit_{i}.log").write_bytes((directory/"compiled/simulate.log").read_bytes())
    passed=all(t["passed"] for t in traces[1:])
    record={**discovery,"traces":traces,"audit_pass":passed,"accepted":passed,
            "status":"ALL_SEALED_TRACES_PASS" if passed else "AUDIT_FAILED",
            "oracle_depends_on_corrected_trace_values":True,"formal_proof":False}
    write_json(directory/"evaluation.json",record);return record


def choose(order, evaluate_discovery, cap=8):
    """Selection sees discovery only. It cannot request an audit or retry on one."""
    attempted=[]
    for identity in order[:cap]:
        result=evaluate_discovery(identity);attempted.append(identity)
        if result["discovery_pass"]:
            return identity,attempted
    return None,attempted
