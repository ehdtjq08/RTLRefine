"""Original-source dependency evidence and structural scope, never patch scores."""
from __future__ import annotations

from collections import defaultdict
import heapq
import re

from ..common import sha256

CLOCK_PORTS={"C","CLK","RD_CLK","WR_CLK"}


def source_ranges(src):
    return [(int(a),int(b)) for a,b in re.findall(r"(?:^|\|)candidate\.v:(\d+)(?:\.\d+)?-(\d+)(?:\.\d+)?",src)]


def dependency_evidence(module, failure, max_state=12, max_cells=80):
    """Bounded static overapproximation, not measured dynamic causality."""
    port=module['ports'].get(failure['port'])
    if not port:return []
    changed=failure['expected'] ^ failure['actual']
    starts=[b for i,b in enumerate(port['bits']) if isinstance(b,int) and (changed>>i)&1]
    if not starts:starts=[b for b in port['bits'] if isinstance(b,int)]
    drivers=defaultdict(list)
    cells=module.get('cells',{})
    for name,cell in cells.items():
        for p,direction in cell.get('port_directions',{}).items():
            if direction=='output':
                for bit in cell['connections'].get(p,[]):
                    if isinstance(bit,int):drivers[bit].append(name)
    queue=[(0,0,b) for b in starts];heapq.heapify(queue);seen={};cell_seen={};result=[]
    while queue:
        state,depth,bit=heapq.heappop(queue)
        if state>max_state or depth>max_cells or seen.get(bit,(999,999))<=(state,depth):continue
        seen[bit]=(state,depth)
        for name in drivers[bit]:
            if cell_seen.get(name,(999,999))<=(state,depth):continue
            cell_seen[name]=(state,depth);cell=cells[name]
            ranges=source_ranges(str(cell.get('attributes',{}).get('src','')))
            for first,last in ranges:
                result.append({'first_line':first,'last_line':last,'state_edges':state,'cell_edges':depth,
                               'failure_port':failure['port'],'failure_cycle':failure['cycle'],
                               'evidence_type':'bounded_static_dependency_overapproximation'})
            sequential=bool(re.search(r'dff|latch|\$ff|\$mem',cell['type'],re.I))
            for p,direction in cell.get('port_directions',{}).items():
                if direction!='input' or p in CLOCK_PORTS:continue
                for parent in cell['connections'].get(p,[]):
                    if isinstance(parent,int):heapq.heappush(queue,(state+sequential,depth+1,parent))
    return result


def edit_signature(item):
    if item['family']=='reset_completion':
        atoms=[]
        for e in item['edits']:
            for name in re.findall(r'\b(\w+)\s*<=',e['replacement']):atoms.append((e['start'],e['end'],name))
        return frozenset(atoms)
    return frozenset((e['start'],e['end'],e['replacement']) for e in item['edits'])


def changed_targets(source,item):
    names=set()
    for edit in item['edits']:
        prefix=source[source.rfind('\n',0,edit['start'])+1:edit['start']]
        matches=re.findall(r'\b(\w+)\s*(?:\[[^\]]+\])?\s*(?:<=|=(?!=))',prefix)
        if matches:names.add(matches[-1])
        for line in edit['replacement'].splitlines():
            if ';' in line:
                names.update(re.findall(r'\b(\w+)\s*(?:\[[^\]]+\])?\s*(?:<=|=(?!=))',line))
    return sorted(names)


def build_cards(source, pool, module, mismatches):
    failures=mismatches[:3];evidence=[e for failure in failures for e in dependency_evidence(module,failure)]
    signatures={p['id']:edit_signature(p) for p in pool}
    cards=[]
    for p in pool:
        lines=[]
        for e in p['edits']:
            first=source.count('\n',0,e['start'])+1;last=source.count('\n',0,max(e['start'],e['end']-1))+1
            lines.append((first,last))
        hits=[e for e in evidence if any(a<=e['last_line'] and b>=e['first_line'] for a,b in lines)]
        closest=min(hits,key=lambda e:(e['state_edges'],e['cell_edges'])) if hits else None
        # Related multi-site variants are available in the same source-only pool.
        # Coverage is a structural preference, not proof that all sites must change.
        supersets=[q for q in pool if q['family']==p['family'] and signatures[p['id']] < signatures[q['id']]]
        max_sites=max([len(signatures[p['id']])]+[len(signatures[q['id']]) for q in supersets])
        completeness=len(signatures[p['id']])/max_sites
        relevance=0 if closest is None else 1/(1+closest['state_edges']+.1*closest['cell_edges'])
        minimality=1/(1+len(p['edits']))
        targets=changed_targets(source,p)
        normalized={re.sub(r'_(?:next|reg)$','',n) for n in targets}
        direct=any(f['port'] in targets or f['port'] in normalized for f in failures)
        score=4*relevance+2*completeness+.5*minimality+2*direct
        cards.append({'id':'patch_'+p['rtl_sha256'][:12],'legacy_id':p['id'],'family':p['family'],'line':p['line'],
                      'note':p['note'],'edits':p['edits'],'rtl_sha256':p['rtl_sha256'],
                      'failure_anchors':failures,'dependency':closest,
                      'structural_coverage':{'fraction':completeness,'edited_sites':len(signatures[p['id']]),
                                             'available_related_sites':max_sites,'superset_ids':[q['id'] for q in supersets]},
                      'changed_targets':targets,'direct_failure_target':direct,
                      'heuristic_components':{'relevance':relevance,'structural_completeness':completeness,'minimality':minimality,'direct_failure_target':int(direct)},
                      'heuristic_score':score,'evidence_limit':'Static source ranges can be coarse; structural bundles need not be semantically required.'})
    if len({c['id'] for c in cards})!=len(cards):raise ValueError('Content-ID collision')
    return cards


def heuristic_order(cards):
    return [c['id'] for c in sorted(cards,key=lambda c:(-c['heuristic_score'],c['rtl_sha256']))]


def size_order(cards):
    return [c['id'] for c in sorted(cards,key=lambda c:(len(c['edits']),sum(abs(e['end']-e['start'])+len(e['replacement']) for e in c['edits']),c['rtl_sha256']))]
