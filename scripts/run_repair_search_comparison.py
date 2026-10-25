"""Same-pool, same-candidate-cap static search versus NVIDIA prioritization."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path
import threading
import time

from rtl_agent.budget import BudgetLedger
from rtl_agent.common import ROOT,new_run_dir,sha256,write_json
from rtl_agent.model_client import ModelError
from rtl_agent.known_bugs_v2.cases import DATA,load
from rtl_agent.known_bugs_v2.evaluator import feedback
from rtl_agent.repair_search.execution import discover,audit,choose
from rtl_agent.repair_search.planner import RankingClient,MODEL,MAX_TOKENS,SETTINGS,messages,parse,guided_order

CAP=8
PREFIX=2
SPEND_CAP=3.0


def run_case(entry,pools,root,reserve,settle):
    identity=entry["case_id"];case=load(identity);directory=root/entry["opaque_id"];directory.mkdir()
    source=(DATA/identity/"input.v").read_text();deps=(DATA/identity/"dependencies.v").read_text()
    (directory/"original.v").write_text(source)
    pool=json.loads((pools/entry["opaque_id"]/"pool.json").read_text());by_id={p["id"]:p for p in pool};ids=list(by_id)
    write_json(directory/"candidate_menu.json",[{k:v for k,v in p.items() if k!="rtl"} for p in pool])
    baseline=discover(identity,source,directory/"original_discovery")
    if baseline["status"] in ("COMPILE_FAILED","POLICY_REJECTED") or not baseline["traces"]:
        raise RuntimeError("Qualified original no longer executes; do not run model")
    plan={"status":"NOT_REQUIRED","api_requests":0,"cost":None,"ranked_ids":[],"wall_seconds":0}
    if not baseline["discovery_pass"] and len(ids)>PREFIX:
        prompt=messages(case,source,deps,pool,feedback(baseline))
        encoded=json.dumps(prompt)
        if any(v in encoded for v in ("control_sources",identity,"trace_1/","trace_2/","unexposed_payload_transform_")):
            raise ValueError("Evaluation-only data entered ranking prompt")
        write_json(directory/"ranking_messages.json",prompt)
        reserve()
        client=RankingClient(ids);before=client.inference_requests;start=time.monotonic()
        try:
            response=client.generate(prompt,max_tokens=MAX_TOKENS);write_json(directory/"ranking_response.json",response)
            proposal=parse(response,ids);write_json(directory/"ranking_proposal.json",proposal)
            plan.update({"status":"VALID","ranked_ids":proposal["ranked_ids"],"explanation":proposal["explanation"]})
        except (ModelError,ValueError,KeyError,IndexError,TypeError,OSError) as exc:
            plan.update({"status":"ERROR_STATIC_FALLBACK","error":client.redact(str(exc))})
        finally:
            plan.update({"api_requests":client.inference_requests-before,"cost":client.last_cost,"wall_seconds":round(time.monotonic()-start,4)})
            settle(entry["opaque_id"],plan)
    write_json(directory/"ranking.json",plan)
    orders={"static_search":ids,"nvidia_prioritized":guided_order(ids,plan["ranked_ids"],PREFIX)}
    write_json(directory/"orders_before_candidate_execution.json",orders)
    cache={};selected={};arms={}
    def evaluate_candidate(key):
        if key not in cache:
            cache[key]=discover(identity,by_id[key]["rtl"],directory/key)
            print({"case":entry["opaque_id"],"candidate":key,"family":by_id[key]["family"],"status":cache[key]["status"]},flush=True)
        return cache[key]
    branches=["static_search","nvidia_prioritized"]
    if int(entry["opaque_id"].split("_")[-1])%2==0:branches.reverse()
    for method in branches:
        if baseline["discovery_pass"]:
            selected[method]="original";attempted=[]
        else:
            selected[method],attempted=choose(orders[method],evaluate_candidate,CAP)
        arms[method]={"selected_id":selected[method],"attempted_ids":attempted,"logical_candidate_evaluations":len(attempted)}
    # BOTH orders and selections are final before any selected-source audit runs.
    write_json(directory/"selections_before_audit.json",arms)
    audited={}
    for key in sorted(set(s for s in selected.values() if s)):
        audited[key]=audit(identity,baseline if key=="original" else cache[key])
    for method,arm in arms.items():
        key=arm["selected_id"]
        result=audited.get(key)
        arm.update({"accepted":bool(result and result["accepted"]),"status":result["status"] if result else "SEARCH_EXHAUSTED" if ids else "NO_GRAMMAR_CANDIDATES",
                    "source_changed":bool(key and key!="original"),"selected_source":f"{entry['opaque_id']}/original_discovery/candidate.v" if key=="original" else f"{entry['opaque_id']}/{key}/candidate.v" if key else None,
                    "discovery_pass_audit_rejected":bool(result and not result["audit_pass"]),
                    "selected_family":by_id[key]["family"] if key in by_id else None,
                    "logical_discovery_tool_seconds":round(sum(sum(c["elapsed_seconds"] for c in cache[i].get("commands",[]))+sum(t["command"]["elapsed_seconds"] for t in cache[i]["traces"]) for i in arm["attempted_ids"]),4)})
    record={**entry,"pool_candidates":len(pool),"ranking":plan,"arms":arms,"physical_candidate_evaluations":len(cache),
            "original_status":baseline["status"],"audits_ran_only_after_both_selections":True}
    write_json(directory/"case.json",record)
    print({"case_complete":entry["opaque_id"],"accepted":{m:a["accepted"] for m,a in arms.items()},"logical_evaluations":{m:a["logical_candidate_evaluations"] for m,a in arms.items()}},flush=True)
    return record


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--pools",required=True);parser.add_argument("--output",required=True);args=parser.parse_args()
    pools=Path(args.pools).resolve();prepared=json.loads((pools/"manifest.json").read_text())
    frozen=json.loads((DATA/"FROZEN.json").read_text())
    for n,h in prepared["generator_hashes"].items():
        if sha256((ROOT/n).read_bytes())!=h:raise ValueError("Generator changed after pool preparation")
    for e in prepared["cases"]:
        if sha256((pools/e["opaque_id"]/"pool.json").read_bytes())!=e["pool_sha256"]:raise ValueError("Prepared pool changed")
    for n,h in frozen["files"].items():
        if sha256((DATA/n).read_bytes())!=h:raise ValueError("V2 source/oracle changed")
    root=new_run_dir("repair_search_comparison",args.output);snapshot=root/"controller_source";snapshot.mkdir()
    files=list((ROOT/"rtl_agent/repair_search").glob("*.py"))+[Path(__file__).resolve(),ROOT/"scripts/prepare_repair_search.py"]
    files += [ROOT/n for n in frozen["checker_hashes"]]
    files += [ROOT/n for n in ("rtl_agent/model_client.py","rtl_agent/model_settings.py","rtl_agent/budget.py","configs/budget.json","configs/pricing.json")]
    hashes={}
    for file in sorted(set(files)):
        relative=str(file.relative_to(ROOT));content=file.read_bytes();(snapshot/relative.replace("/","__")).write_bytes(content);hashes[relative]=sha256(content)
    protocol={"methods":["static_search","nvidia_prioritized"],"same_static_pool":True,"candidate_cap_per_arm":CAP,"common_static_prefix":PREFIX,
              "baseline_original_gate_shared":True,"NVIDIA_role":"One pre-execution ranking of existing IDs, never source generation","max_model_calls":9,
              "model":MODEL,"settings":SETTINGS.to_dict(),"max_output_tokens":MAX_TOKENS,"estimated_spend_cap_usd":SPEND_CAP,
              "candidate_order":"Round-robin grammar families, source order inside family; NVIDIA can reorder after common prefix; unlisted IDs retain static order",
              "invalid_ranking":"Explicit static fallback; not credited as model benefit","stop":"First discovery pass; no audit-driven retry",
              "audit":"Only after both selections fixed; V2 oracle and data unchanged","shared_native_cache":"Physical evaluations counted once; each method charged its logical candidate/tool cost",
              "counterfactual_timing":"Cached execution means logical tool time is not measured independent end-to-end speedup",
              "SMT_used":False,"pool_manifest":prepared,"pool_manifest_sha256":sha256((pools/"manifest.json").read_bytes()),"controller_hashes":hashes,
              "scope":"Known development cases after V2 analysis and one retention pilot. Fixed lexical edit grammar; not unseen accuracy, a new algorithm, unbounded proof or a fair same-compute comparison against the older two-call V2 study."}
    write_json(root/"protocol.json",protocol);ledger=BudgetLedger();write_json(root/"budget_before.json",ledger.summary())
    RankingClient(["catalog_check"]).verify_model()
    condition=threading.Condition();active=[0];paid=[];rows=[]
    maximum=ledger.quote(MODEL,MAX_TOKENS)["reserved_usd"]
    def reserve():
        with condition:
            while True:
                spent=sum((r["cost"].get("estimated_usd") if r["cost"].get("estimated_usd") is not None else r["cost"]["reserved_usd"]) for r in paid if r["cost"])
                if spent+maximum*(active[0]+1)<=SPEND_CAP:active[0]+=1;return
                if not active[0]:raise RuntimeError("Ranking experiment budget exhausted")
                condition.wait(timeout=1)
    def settle(case,plan):
        with condition:
            if plan["api_requests"]:paid.append({"case":case,"api_requests":plan["api_requests"],"cost":plan["cost"]})
            active[0]-=1;write_json(root/"paid_requests.json",paid);condition.notify_all()
    status="COMPLETE";errors=[]
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures={executor.submit(run_case,e,pools,root,reserve,settle):e["opaque_id"] for e in prepared["cases"]}
        for future in as_completed(futures):
            try:rows.append(future.result())
            except Exception as exc:status="INCOMPLETE";errors.append({"case":futures[future],"error":str(exc)});write_json(root/"errors.json",errors)
            write_json(root/"progress.json",{"cases":rows,"paid_requests":paid})
    for n,h in hashes.items():
        if sha256((ROOT/n).read_bytes())!=h:raise ValueError("Controller changed during study")
    for n,h in frozen["files"].items():
        if sha256((DATA/n).read_bytes())!=h:raise ValueError("V2 oracle/data changed")
    for e in prepared["cases"]:
        if sha256((pools/e["opaque_id"]/"pool.json").read_bytes())!=e["pool_sha256"]:raise ValueError("Pool changed during study")
    rows.sort(key=lambda r:r["opaque_id"])
    for row in rows:row["kind"]=load(row["case_id"])["kind"]
    real=[r for r in rows if r["kind"]=="historical_defect"];controls=[r for r in rows if r["kind"]=="normal_control"]
    totals={}
    for method in ("static_search","nvidia_prioritized"):
        totals[method]={"real_trace_passes":sum(r["arms"][method]["accepted"] for r in real),"real_cases":len(real),
            "control_trace_passes":sum(r["arms"][method]["accepted"] for r in controls),"controls":len(controls),
            "logical_candidate_evaluations":sum(r["arms"][method]["logical_candidate_evaluations"] for r in rows),
            "audit_rejected_discovery_passes":sum(r["arms"][method]["discovery_pass_audit_rejected"] for r in rows),
            "logical_discovery_tool_seconds":round(sum(r["arms"][method]["logical_discovery_tool_seconds"] for r in rows),4)}
    paired={"both_pass":0,"static_only":0,"nvidia_only":0,"both_fail":0}
    for r in real:
        a,b=r["arms"]["static_search"]["accepted"],r["arms"]["nvidia_prioritized"]["accepted"]
        paired["both_pass" if a and b else "static_only" if a else "nvidia_only" if b else "both_fail"]+=1
    report={"status":status,"cases":rows,"totals":totals,"paired_real_outcomes":paired,"physical_candidate_evaluations":sum(r["physical_candidate_evaluations"] for r in rows),
            "valid_rankings":sum(r["ranking"]["status"]=="VALID" for r in rows),"ranking_fallbacks":sum(r["ranking"]["status"]=="ERROR_STATIC_FALLBACK" for r in rows),
            "unique_model_calls":sum(r["api_requests"] for r in paid),"estimated_api_cost_usd":sum((r["cost"] or {}).get("estimated_usd") or 0 for r in paid),
            "unsettled_requests":sum(not r["cost"] or r["cost"].get("estimated_usd") is None for r in paid),"source_pool_and_V2_seals_unchanged":True,"scope":protocol["scope"]}
    write_json(root/"summary.json",report);write_json(root/"budget_after.json",ledger.summary())
    print(json.dumps({k:report[k] for k in ("status","totals","paired_real_outcomes","unique_model_calls","estimated_api_cost_usd")},indent=2))


if __name__=="__main__":main()
