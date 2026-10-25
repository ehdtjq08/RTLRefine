"""Rank an existing pool with machine facts and optional audited model views."""
from __future__ import annotations

import json
from pathlib import Path
import random
import time

from ..budget import BudgetLedger
from ..common import sha256,write_json
from .features import build_cards,heuristic_order
from .aggregate import consensus
from .model_ids import EvidenceClient,MAX_TOKENS,messages,parse


def rank_existing_pool(case,source,dependencies,pool,netlist,discovery,directory,*,live=False,seed=20261023):
    """No candidate execution or private labels are accepted by this API.

    The caller supplies the original public discovery and original netlist.
    Changing menu order probes repeatability, not calibrated correctness.
    """
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    if not discovery.get('traces'):
        raise ValueError('A checked public discovery trace is required')
    if discovery['traces'][0].get('passed'):
        result={'order':[],'cards':[],'api_requests':0,'original_trace_pass':True,
                'source_sha256':sha256(source.encode()),'scope':'Original passes this public profile; no repair ranking is requested.'}
        write_json(directory/'ranking.json',result)
        return result
    if not 1<=len(pool)<=128 or len({p['id'] for p in pool})!=len(pool):
        raise ValueError('Supply one to 128 uniquely identified candidates')
    for item in pool:
        if sha256(item['rtl'].encode())!=item['rtl_sha256']:
            raise ValueError('Candidate source does not match its content hash')
        edits=sorted(item['edits'],key=lambda e:e['start'])
        if any(a['end']>b['start'] for a,b in zip(edits,edits[1:])):
            raise ValueError('Overlapping candidate edits')
        applied=source
        for edit in reversed(edits):
            if not 0<=edit['start']<=edit['end']<=len(source) or source[edit['start']:edit['end']]!=edit['old']:
                raise ValueError('Candidate edit is not anchored in the checked source')
            applied=applied[:edit['start']]+edit['replacement']+applied[edit['end']:]
        if applied!=item['rtl']:
            raise ValueError('Candidate edits do not produce its recorded source')
    failures=discovery['traces'][0]['first_mismatches']
    cards=build_cards(source,pool,netlist,failures)
    write_json(directory/'cards.json',cards)
    baseline=heuristic_order(cards);views=[];start=time.monotonic()
    if live and failures:
        ports=sorted({f['port'] for f in failures});ids=[c['id'] for c in cards]
        verifier=EvidenceClient(ids,ports);verifier.verify_model()
        # Reserve conservatively for all three requests before beginning.
        ledger=BudgetLedger();quote=ledger.quote(verifier.model_id,MAX_TOKENS)
        remaining=ledger.summary()
        required=quote['reserved_usd']*3
        if required>min(4.,remaining['remaining_usd'],remaining['phase_remaining_usd']):
            raise ValueError('Insufficient remaining budget for three bounded ranking requests')
        for view in range(3):
            folder=directory/f'view_{view+1}';folder.mkdir()
            menu=sorted(cards,key=lambda c:c['id']);random.Random(seed+view*17).shuffle(menu)
            prompt=messages(case,source,dependencies,menu,discovery)
            write_json(folder/'messages.json',prompt)
            client=EvidenceClient(ids,ports);result={'status':'ERROR','ids':[]}
            try:
                response=client.generate(prompt,max_tokens=MAX_TOKENS);write_json(folder/'response.json',response)
                proposal=parse(response,cards,ports);write_json(folder/'proposal.json',proposal)
                result.update({'status':'VALID','ids':[v['id'] for v in proposal['ranking']],'proposal':proposal})
            except Exception as exc:
                result['error']=client.redact(type(exc).__name__+': '+str(exc))
            result.update({'cost':client.last_cost,'api_requests':client.inference_requests})
            write_json(folder/'ranking.json',result);views.append(result)
    ranked=consensus(cards,views)
    result={**ranked,'cards':cards,'heuristic_order':baseline,'source_sha256':sha256(source.encode()),
            'views':views,'api_requests':sum(v['api_requests'] for v in views),
            'wall_seconds':round(time.monotonic()-start,4),'model_mechanisms_are_unverified':True,
            'original_trace_pass':False,'scope':'Ranks a supplied finite pool from public observations; does not establish correctness or grammar coverage.'}
    write_json(directory/'ranking.json',result)
    return result
