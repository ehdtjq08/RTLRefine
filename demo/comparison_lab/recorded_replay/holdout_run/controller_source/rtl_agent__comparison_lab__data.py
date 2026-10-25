"""Separate public ranking context from private outcomes; hash both before use."""
from __future__ import annotations

import json
import copy
from pathlib import Path

from ..common import sha256,write_json

CARD_KEYS=('id','legacy_id','family','line','note','edits','rtl_sha256','failure_anchors','dependency',
           'structural_coverage','changed_targets','direct_failure_target','heuristic_components','heuristic_score','evidence_limit')
OBSERVATION_KEYS=('passed','cycles','comparisons','mismatch_count','first_mismatches','input_windows','scope')


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()


def digest(value):return sha256(canonical(value))


def canonical_project(value):
    project=str(value).strip().lower().rstrip('/')
    for prefix in ('https://github.com/','http://github.com/','github.com/'):
        if project.startswith(prefix):project=project[len(prefix):]
    if project.endswith('.git'):project=project[:-4]
    if not project or '\n' in project:raise ValueError('Invalid upstream project identity')
    return project


def public_packet(identity,source,dependencies,case,payload):
    # Allowlist, not a blacklist: audit paths, reference hashes and labels cannot
    # enter through extra case/observation metadata.
    observations=payload['original_discovery'].get('traces',[])[:1]
    packet={'id':identity,'source':source,'dependencies':dependencies,
        'case':{k:case[k] for k in ('id','top','clock','ports')},
        'original_pass':bool(payload['original_discovery_pass']),
        'discovery':{'traces':[{k:t[k] for k in OBSERVATION_KEYS if k in t} for t in observations]},
        'cards':[{k:c[k] for k in CARD_KEYS if k in c} for c in payload['cards']],
        'orders':{k:payload[k] for k in ('source_order','size_order','heuristic_order')}}
    validate_public(packet);return packet


def validate_public(packet):
    if set(packet)!={'id','source','dependencies','case','original_pass','discovery','cards','orders'}:
        raise ValueError('Unexpected public-context field')
    if len(packet['source'].encode())>90000 or len(packet['cards'])>128:raise ValueError('Unsupported source or pool size')
    ids=[c['id'] for c in packet['cards']]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate candidate identity')
    if any(set(c)-set(CARD_KEYS) for c in packet['cards']):raise ValueError('Unexpected candidate metadata')
    if set(packet['case'])!={'id','top','clock','ports'}:raise ValueError('Private case metadata in public context')
    if any(set(t)-set(OBSERVATION_KEYS) for t in packet['discovery']['traces']):raise ValueError('Private observation metadata')
    for order in packet['orders'].values():
        if len(order)!=len(ids) or set(order)!=set(ids):raise ValueError('Baseline is not a complete permutation')
    return packet


def create_bundle(directory,public,private,metadata):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    if {p['id'] for p in public}!=set(private):raise ValueError('Public/private task mismatch')
    if len(public)!=len(private):raise ValueError('Duplicate task')
    metadata=copy.deepcopy(metadata)
    if set(metadata.get('cases',{}))!=set(private):raise ValueError('Incomplete project/stratum metadata')
    for case in metadata['cases'].values():case['project']=canonical_project(case['project'])
    if not metadata.get('cohort') or not metadata.get('claim_scope'):raise ValueError('Declare cohort and claim scope')
    kinds={c['kind'] for c in metadata['cases'].values()}
    if not kinds<={'historical_known_defect','synthetic_injected','normal_control'}:raise ValueError('Explicit defect/control provenance required')
    if len(kinds-{'normal_control'})>1:raise ValueError('Register historical and synthetic cohorts separately')
    if any(c.get('solution_seeded') for c in metadata['cases'].values()) and not metadata['claim_scope'].startswith('conditional'):
        raise ValueError('Seeded solutions only support a conditional ranking claim')
    source_groups={}
    for packet in public:
        validate_public(packet);labels=private[packet['id']]['labels']
        source_hash=sha256(packet['source'].encode());group=metadata['cases'][packet['id']]['project']
        if source_hash in source_groups and source_groups[source_hash]!=group:raise ValueError('Identical source cannot count as independent projects')
        source_groups[source_hash]=group
        if set(labels)!={c['id'] for c in packet['cards']}:raise ValueError('Incomplete candidate catalog')
        if any(type(v.get('accepted')) is not bool or type(v.get('discovery_pass')) is not bool for v in labels.values()):raise ValueError('Candidate outcomes must be Boolean')
        if any(bool(v['accepted']) and not v['discovery_pass'] for v in labels.values()):raise ValueError('Audit acceptance requires discovery pass')
    (directory/'public.json').write_bytes(canonical(public)+b'\n')
    (directory/'private.json').write_bytes(canonical(private)+b'\n')
    write_json(directory/'metadata.json',metadata)
    seal={name:sha256((directory/name).read_bytes()) for name in ('public.json','private.json','metadata.json')}
    write_json(directory/'SEAL.json',seal)
    return directory


def verify_bundle(directory,*,include_private=False):
    directory=Path(directory);seal=json.loads((directory/'SEAL.json').read_text())
    for name,expected in seal.items():
        if name not in ('public.json','private.json','metadata.json'):
            raise ValueError('Unexpected dataset seal entry')
        if name=='private.json' and not include_private:continue
        if sha256((directory/name).read_bytes())!=expected:
            raise ValueError('Dataset seal changed: '+name)
    if set(seal)!={'public.json','private.json','metadata.json'}:raise ValueError('Incomplete dataset seal')
    return digest(seal)


def load_public(directory):
    directory=Path(directory);verify_bundle(directory)
    packets=json.loads((directory/'public.json').read_text())
    for p in packets:validate_public(p)
    return packets,json.loads((directory/'metadata.json').read_text())


def load_private(directory):
    directory=Path(directory);verify_bundle(directory,include_private=True)
    return json.loads((directory/'private.json').read_text())
