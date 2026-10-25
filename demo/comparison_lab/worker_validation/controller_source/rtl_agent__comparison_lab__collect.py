"""Collect complete plans without opening private outcomes; resume paid calls safely."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import random
import time

from ..budget import BudgetLedger,BudgetError
from ..common import ROOT,sha256
from ..evidence_ranking.model_ids import EvidenceClient,MAX_TOKENS,messages,parse
from .data import load_public,digest
from .policies import static_orders,model_orders,complete
from .protocol import load_protocol


def atomic_json(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w') as f:
        json.dump(value,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)


@contextmanager
def exclusive(run):
    with (Path(run)/'RUN.lock').open('a') as f:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Another process owns this run') from None
        try:yield
        finally:fcntl.flock(f,fcntl.LOCK_UN)


def accounted(cost):
    if cost is None:return None
    return cost.get('estimated_usd') if cost.get('estimated_usd') is not None else cost.get('reserved_usd')


def view_cost(views):
    if not views:return 0.
    amounts=[accounted(v.get('cost')) for v in views]
    return None if any(x is None for x in amounts) else sum(amounts)


def _live_view(packet,family,menu,folder,protocol,run):
    prompt=messages(packet['case'],packet['source'],packet['dependencies'],menu,packet['discovery'],include_evidence=family=='evidence')
    request_hash=digest(prompt);request=folder/'REQUEST_STARTED.json';response_file=folder/'response.json'
    if request.exists():
        prior=json.loads(request.read_text())
        if prior['prompt_sha256']!=request_hash:raise ValueError('Pending prompt changed')
        if not response_file.exists() and prior.get('request_may_have_been_sent',True):
            raise ValueError('Unresolved paid request; no automatic repeat: '+str(folder))
    if not response_file.exists():
        ledger=BudgetLedger();quote=ledger.quote(protocol['model'],MAX_TOKENS)
        costs=[json.loads(p.read_text()).get('cost') for p in Path(run).glob('plans/*/trial_*/*/view_*/ranking.json')]
        spent=sum(accounted(c) or 0 for c in costs)
        if spent+quote['reserved_usd']>protocol['run_api_cap_usd']:raise BudgetError('Registered run cap cannot reserve another bounded request')
        ports=sorted({m['port'] for t in packet['discovery']['traces'] for m in t.get('first_mismatches',[])})
        client=EvidenceClient([c['id'] for c in menu],ports)
        atomic_json(folder/'messages.json',prompt)
        atomic_json(request,{'prompt_sha256':request_hash,'request_may_have_been_sent':True})
        start=time.monotonic()
        try:
            response=client.generate(prompt,max_tokens=MAX_TOKENS)
            # Persist provider text before parsing, so parser changes/restarts
            # never cause another inference request for the same cell.
            atomic_json(response_file,response)
            atomic_json(folder/'cost.json',{'cost':client.last_cost,'wall_seconds':time.monotonic()-start})
        except BudgetError:
            atomic_json(request,{'prompt_sha256':request_hash,'request_may_have_been_sent':False,'budget_blocked_before_request':True})
            raise
        except Exception as exc:
            result={'status':'ERROR','ids':[],'error':client.redact(type(exc).__name__+': '+str(exc)),
                'cost':client.last_cost,'wall_seconds':time.monotonic()-start,'api_requests':client.inference_requests,'origin':'live_nebius'}
            atomic_json(folder/'ranking.json',result);return result
    if not (folder/'cost.json').exists():
        raise ValueError('Response saved but cost checkpoint unresolved; do not repeat the request')
    response=json.loads(response_file.read_text());cost=json.loads((folder/'cost.json').read_text())
    result={'status':'ERROR','ids':[],'origin':'live_nebius','api_requests':1,**cost}
    try:
        value=parse(response,packet['cards'],[])
        result.update({'status':'VALID','ids':[r['id'] for r in value['ranking']],'proposal':value})
    except (ValueError,KeyError,TypeError) as exc:result['error']=type(exc).__name__+': '+str(exc)
    atomic_json(folder/'ranking.json',result);return result


def collect(run,*,live_adapter=None):
    run=Path(run)
    with exclusive(run):
        protocol=load_protocol(run);packets,metadata=load_public(protocol['bundle'])
        if (run/'PLANS_SEALED.json').exists():
            verify_plans(run);return {'status':'ALREADY_COMPLETE','new_model_calls':0}
        recorded=None
        if protocol['provider']=='recorded':
            path=Path(protocol['bundle'])/'recorded_views.json'
            if sha256(path.read_bytes())!=protocol['recorded_views_sha256']:raise ValueError('Recorded input changed')
            recorded=json.loads(path.read_text())
        actual_new=0
        for packet in packets:
            for trial in range(protocol['trials']):
                folder=run/'plans'/packet['id']/f'trial_{trial+1}';folder.mkdir(parents=True,exist_ok=True)
                if (folder/'plan.json').exists():continue
                orders=static_orders(packet);raw=[];evidence=[];available={m:True for m in protocol['methods']}
                rank_random=list(packet['orders']['source_order'])
                stable_seed=int(sha256(packet['id'].encode())[:12],16)+protocol['seed']+trial*997
                random.Random(stable_seed).shuffle(rank_random);orders['random_order']=rank_random
                if packet['cards'] and not packet['original_pass']:
                    for view in range(3):
                        menu=sorted(packet['cards'],key=lambda c:c['id']);random.Random(stable_seed+view*17).shuffle(menu)
                        for family,views in (('raw',raw),('evidence',evidence)):
                            current=folder/family/f'view_{view+1}';current.mkdir(parents=True,exist_ok=True);saved=current/'ranking.json'
                            if saved.exists():result=json.loads(saved.read_text())
                            elif recorded is not None:
                                prior=recorded[packet['id']][family]
                                if view>=len(prior):continue
                                result={**prior[view],'origin':'recorded_replay','api_requests':0}
                                atomic_json(saved,result)
                            else:
                                adapter=live_adapter or _live_view
                                result=adapter(packet,family,menu,current,protocol,run)
                                actual_new+=result.get('api_requests',0)
                                atomic_json(saved,result)
                            if result['status']=='VALID':complete(result['ids'],packet['orders']['heuristic_order'])
                            views.append(result)
                    extra,gates=model_orders(packet,raw,evidence);orders.update(extra)
                    available['raw_single']=len(raw)>=1
                    available['raw_consensus']=len(raw)==3
                    available['evidence_single']=len(evidence)>=1
                    for m in ('evidence_consensus','evidence_ungated'):available[m]=len(evidence)==3
                else:
                    gates={};orders.update({m:packet['orders']['heuristic_order'] for m in ('raw_single','raw_consensus','evidence_single','evidence_ungated','evidence_consensus')})
                costs={m:0. for m in protocol['methods']};latency={m:0. for m in protocol['methods']};calls={m:0 for m in protocol['methods']}
                for method,views in (('raw_single',raw[:1]),('raw_consensus',raw),('evidence_single',evidence[:1]),('evidence_consensus',evidence),('evidence_ungated',evidence)):
                    costs[method]=view_cost(views);latency[method]=sum(v.get('wall_seconds',0) for v in views);calls[method]=len(views)
                policy_error=None
                if protocol.get('candidate_policy'):
                    declared=protocol['candidate_views'];inputs={};used=[]
                    for family,rows in (('raw',raw),('evidence',evidence)):
                        if declared in (family,'both'):
                            inputs[family]=[{k:v[k] for k in ('status','ids','proposal') if k in v} for v in rows];used+=rows
                    available['candidate']=not packet['cards'] or packet['original_pass'] or ((declared not in ('raw','both') or len(raw)==3) and (declared not in ('evidence','both') or len(evidence)==3))
                    orders['candidate']=packet['orders']['heuristic_order']
                    costs['candidate']=view_cost(used);latency['candidate']=sum(v.get('wall_seconds',0) for v in used);calls['candidate']=len(used)
                    if packet['cards'] and not packet['original_pass'] and available['candidate']:
                        from .isolated_policy import run_policy
                        try:
                            order,seconds=run_policy(ROOT/protocol['candidate_policy'],packet,inputs,stable_seed,folder/'candidate_worker')
                            orders['candidate']=order;latency['candidate']+=seconds
                        except ValueError as exc:policy_error=str(exc)
                atomic_json(folder/'plan.json',{'id':packet['id'],'trial':trial+1,'public_sha256':digest(packet),'orders':orders,
                    'available':available,'api_cost_usd':costs,'ranking_wall_seconds':latency,'logical_model_calls':calls,'gates':gates,
                    'view_errors':sum(v['status']!='VALID' for v in raw+evidence),'candidate_policy_error':policy_error})
        load_protocol(run) # refuse a mid-collection implementation/data edit
        plans={str(p.relative_to(run)):sha256(p.read_bytes()) for p in sorted((run/'plans').rglob('*')) if p.is_file()}
        atomic_json(run/'PLANS_SEALED.json',{'protocol_sha256':digest(protocol),'files':plans,
            'private_outcomes_opened_during_collection':False,'expected_plan_count':len(packets)*protocol['trials']})
        return {'status':'COMPLETE','new_model_calls':actual_new,'plans':len(packets)*protocol['trials']}


def verify_plans(run):
    run=Path(run);protocol=load_protocol(run)
    if not (run/'PLANS_SEALED.json').exists():raise ValueError('All paired plans must be sealed before outcome analysis')
    seal=json.loads((run/'PLANS_SEALED.json').read_text())
    if digest(protocol)!=seal['protocol_sha256']:raise ValueError('Plan belongs to another protocol')
    actual={str(p.relative_to(run)) for p in (run/'plans').rglob('*') if p.is_file()}
    if actual!=set(seal['files']):raise ValueError('Plan file set changed')
    for relative,expected in seal['files'].items():
        if sha256((run/relative).read_bytes())!=expected:raise ValueError('Sealed plan changed')
    plans=[json.loads(p.read_text()) for p in sorted((run/'plans').glob('*/trial_*/plan.json'))]
    packets,_=load_public(protocol['bundle'])
    expected={(p['id'],i+1) for p in packets for i in range(protocol['trials'])}
    if {(p['id'],p['trial']) for p in plans}!=expected or len(plans)!=len(expected):raise ValueError('Incomplete paired run')
    by={p['id']:p for p in packets}
    if any(p['public_sha256']!=digest(by[p['id']]) for p in plans):raise ValueError('Plan public context mismatch')
    return protocol,plans
