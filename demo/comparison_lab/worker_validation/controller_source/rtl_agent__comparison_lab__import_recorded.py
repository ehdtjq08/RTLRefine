"""Import prior evidence as EXPOSED DEVELOPMENT DATA, never fresh test data."""
from __future__ import annotations

import json
from pathlib import Path

from ..common import ROOT,sha256,write_json
from ..known_bugs_v2.cases import DATA,load
from .data import create_bundle,public_packet


def read(p):return json.loads(p.read_text())


def view(row):
    return {k:row[k] for k in ('status','ids','cost','wall_seconds','error') if k in row}


def import_cohort(cohort,destination):
    base=ROOT/'demo/evidence_ranking'/cohort;prepared=read(base/'inputs/manifest.json')
    public=[];private={};case_meta={};recorded={}
    for entry in prepared['cases']:
        identity=entry['opaque_id'];payload=read(base/'inputs'/identity/'rank_input.json')
        if cohort=='development':
            case=load(entry['case_id']);module=case['top'];kind='normal_control' if payload['original_discovery_pass'] else 'historical_known_defect'
            project='ZipCPU/sdspi' if entry['case_id'].startswith('zipcpu') else 'alexforencich/verilog-axis'
        else:
            case=read(base/'inputs'/identity/'case.json');module=case['module_id'];kind='synthetic_injected'
            project={'i2c_master':'alexforencich/verilog-i2c','skidbuffer':'ZipCPU/wb2axip'}.get(module,'alexforencich/verilog-axis')
        source=(base/'inputs'/identity/'candidate.v').read_text();dependencies=(base/'inputs'/identity/'dependencies.v').read_text()
        if payload['original_discovery_pass']:
            payload={**payload,'cards':[],'source_order':[],'size_order':[],'heuristic_order':[]}
        packet=public_packet(identity,source,dependencies,case,payload);public.append(packet)
        labels=read(base/'catalog'/identity/'catalog.json')['candidate_labels']
        converted={}
        for card in packet['cards']:
            label=labels[card['rtl_sha256']];duration=None
            if label.get('commands') and label.get('traces'):
                duration=sum(c.get('elapsed_seconds',0) for c in label['commands'])+sum(t.get('command',{}).get('elapsed_seconds',0) for t in label['traces'])
            converted[card['id']]={'discovery_pass':bool(label['discovery_pass']),'accepted':bool(label['accepted']),
                                   'eda_seconds':duration,'status':label['status']}
        private[identity]={'labels':converted,'original_accepted':bool(payload['original_discovery_pass'])}
        case_meta[identity]={'project':project,'module':module,'kind':kind,'solution_seeded':cohort=='holdout',
            'exposure':'previously_examined','upstream_case':entry['case_id'],'source_sha256':sha256(source.encode())}
        plan=read(base/'plans'/identity/'plans.json')
        if plan['original_pass']:recorded[identity]={'raw':[],'evidence':[]};continue
        # Development had one raw view per trial. Combining those for replay is
        # retrospective, not a contemporaneously paired three-call experiment.
        raw=[view(t['raw']) for t in plan['trials']]
        evidence=[view(v) for v in plan['trials'][0]['views']]
        source_run=base/('raw_plans' if cohort=='development' else 'plans')/identity
        for i,r in enumerate(raw):
            saved=source_run/f'trial_{i+1}/raw_no_features/ranking.json'
            if saved.exists():r.update({k:v for k,v in read(saved).items() if k in ('cost','wall_seconds')})
        for i,r in enumerate(evidence):
            saved=source_run/f'trial_1/evidence_view_{i+1}/ranking.json'
            if saved.exists():r.update({k:v for k,v in read(saved).items() if k in ('cost','wall_seconds')})
        recorded[identity]={'raw':raw,'evidence':evidence}
    if cohort=='holdout':
        # Original reference replays were recorded for all four new modules.
        # Keep those controls rather than importing only the failing mutants.
        for module in sorted({e['module_id'] for e in prepared['cases']}):
            first=next(e for e in prepared['cases'] if e['module_id']==module)
            case=read(base/'inputs'/first['opaque_id']/'case.json');identity='normal_'+module;case['id']=identity
            original=read(base/'inputs'/module/'normal_control/evaluation.json')
            source=(base/'inputs'/module/'reference.v').read_text()
            payload={'cards':[],'source_order':[],'size_order':[],'heuristic_order':[],
                'original_discovery_pass':original['discovery_pass'],'original_discovery':{'traces':original['traces'][:1]}}
            public.append(public_packet(identity,source,'',case,payload))
            private[identity]={'labels':{},'original_accepted':original['accepted']}
            project={'i2c_master':'alexforencich/verilog-i2c','skidbuffer':'ZipCPU/wb2axip'}.get(module,'alexforencich/verilog-axis')
            case_meta[identity]={'project':project,'module':module,'kind':'normal_control','solution_seeded':False,
                'exposure':'previously_examined','source_sha256':sha256(source.encode())}
            recorded[identity]={'raw':[],'evidence':[]}
    metadata={'schema_version':1,'cohort':'historical_development' if cohort=='development' else 'synthetic_seeded_development',
        'exposure':'previously_examined','cases':case_meta,'normal_controls':sum(p['original_pass'] for p in public),
        'source':'demo/evidence_ranking/'+cohort,'recorded_replay_is_not_new_inference':True,
        'recorded_raw_views_are_not_contemporaneously_menu_paired':True,
        'oracle_scope':'Fixed two-state golden traces, not general protocol correctness or unbounded proof',
        'claim_scope':'finite_source_grammar' if cohort=='development' else 'conditional_seeded_pool_ranking'}
    create_bundle(destination,public,private,metadata)
    write_json(Path(destination)/'recorded_views.json',recorded)
    return Path(destination)
