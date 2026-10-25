"""Strong simple baselines and compute-matched model ablations."""
from __future__ import annotations

import copy

from ..evidence_ranking.aggregate import consensus

STATIC=('source_order','size_order','heuristic_order','size_circuit_rrf')
MODEL=('raw_single','raw_consensus','evidence_single','evidence_ungated','evidence_consensus')
ABLATIONS=('without_dependency','without_scope')
METHODS=STATIC+MODEL+ABLATIONS


def complete(order,base):
    if len(order)!=len(set(order)) or any(i not in base for i in order):raise ValueError('Invalid method order')
    return list(order)+[i for i in base if i not in order]


def static_orders(packet):
    result=copy.deepcopy(packet['orders']);base=result['heuristic_order']
    ranks=[{i:r+1 for r,i in enumerate(result[k])} for k in ('size_order','heuristic_order')]
    result['size_circuit_rrf']=sorted(base,key=lambda i:(-sum(1/(60+r[i]) for r in ranks),i))
    cards=packet['cards']
    for method,component,weight in (('without_dependency','relevance',4),('without_scope','structural_completeness',2)):
        result[method]=[c['id'] for c in sorted(cards,key=lambda c:(-(c['heuristic_score']-weight*c['heuristic_components'][component]),c['rtl_sha256']))]
    return result


def model_orders(packet,raw_views,evidence_views):
    cards=packet['cards'];base=packet['orders']['heuristic_order']
    raw=consensus(cards,raw_views);evidence=consensus(cards,evidence_views)
    def first(views):return complete(views[0]['ids'],base) if views and views[0]['status']=='VALID' else base
    # Ungated raw consensus is a strong three-call baseline. If all calls fail,
    # its Borda tie fallback is the same fixed heuristic, with errors counted.
    return {'raw_single':first(raw_views),'raw_consensus':raw['raw_consensus_order'],
        'evidence_single':first(evidence_views),'evidence_ungated':evidence['raw_consensus_order'],
        'evidence_consensus':evidence['order']}, {'raw':raw,'evidence':evidence}
