"""Build complete unseeded candidate catalogs from pinned native trace cases."""
from __future__ import annotations

import json
from pathlib import Path
import re

from ..common import sha256,write_json
from ..evidence_ranking.features import build_cards,heuristic_order,size_order
from ..known_bugs_v2.cases import source_policy
from ..known_bugs_v2.engine import inspect,compile_candidate,run_trace
from ..known_bugs_v2.evaluator import feedback
from ..known_bugs_v2.runner import BenchmarkRunner
from ..repair_search.candidates import make_pool
from .data import create_bundle,public_packet


def evaluate(source,dependencies,original,case,directory,runner):
    directory.mkdir(parents=True)
    record={'discovery_pass':False,'accepted':False,'traces':[],'status':'POLICY_REJECTED','eda_seconds':None}
    try:
        source_policy(source,original,case['ports'])
        compiled=directory/'compiled'
        commands=compile_candidate(source,dependencies,case['ports'],case['clock'],case['top'],compiled,runner)
        record['commands']=commands
        if len(commands)!=2 or commands[-1]['status']!='PASS':record['status']='COMPILE_FAILED'
        else:
            for i,trace in enumerate(case['traces']):
                result=run_trace(compiled,trace,case['top'],runner);record['traces'].append(result)
                (directory/f'trace_{i}.log').write_bytes((compiled/'simulate.log').read_bytes())
                if i==0:
                    record['discovery_pass']=result['passed']
                    if not result['passed']:break
            record['accepted']=len(record['traces'])==3 and all(t['passed'] for t in record['traces'])
            record['status']='ACCEPTED' if record['accepted'] else 'AUDIT_FAILED' if record['discovery_pass'] else 'DISCOVERY_FAILED'
        record['eda_seconds']=sum(c.get('elapsed_seconds',0) for c in commands)+sum(t['command'].get('elapsed_seconds',0) for t in record['traces'])
    except (ValueError,RuntimeError,OSError) as exc:record['error']=str(exc)
    write_json(directory/'evaluation.json',record);return record


def prepare(manifest_file,output,*,study=None):
    manifest_file=Path(manifest_file).resolve();spec=json.loads(manifest_file.read_text());base=manifest_file.parent
    output=Path(output);output.mkdir(parents=True,exist_ok=False);work=output/'native_records';work.mkdir()
    registration=None
    if study:
        from .protocol import verify_study
        registration=verify_study(json.loads(Path(study).read_text()))
        if registration['source_manifest_sha256']!=sha256(manifest_file.read_bytes()):raise ValueError('Registered source manifest changed')
    elif spec['exposure']=='unexamined':
        raise ValueError('Use --study to prepare an unexamined final cohort; development preparation must be labeled exposed')
    runner=BenchmarkRunner();ok,why=runner.probe(work/'isolation')
    if not ok:raise RuntimeError(why)
    if not (runner.version('verilator') or '').startswith('Verilator 4.038 '):raise ValueError('Pinned Verilator 4.038 required')
    public=[];private={};metadata={};input_hashes={}
    for index,item in enumerate(spec['cases'],1):
        identity=item['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+',identity) or not re.fullmatch(r'[A-Za-z_]\w*',item['top']):raise ValueError('Unsafe case or top name')
        folder=work/identity;folder.mkdir()
        def source_file(relative):
            path=(base/relative).resolve()
            if not path.is_relative_to(base):raise ValueError('Case path outside manifest directory')
            input_hashes[str(path.relative_to(base))]=sha256(path.read_bytes());return path
        source=source_file(item['source']).read_text()
        dependencies=source_file(item['dependencies']).read_text() if item.get('dependencies') else ''
        case={'id':identity,'top':item['top'],'clock':item['clock'],'ports':item.get('ports',{}),'traces':[]}
        for trace in item['traces']:
            case['traces'].append({**trace,'stimulus':str(source_file(trace['stimulus'])),'expected':str(source_file(trace['expected']))})
        if len(case['traces'])!=3:raise ValueError('Exactly one discovery and two passive audit profiles required')
        pool=[];cards=[];original={'discovery_pass':False,'accepted':False,'traces':[]};labels={};error=None
        try:
            ports=inspect(source,dependencies,case['top'],folder/'original_inspection',runner);case['ports']=ports
            source_policy(source,source,ports)
            for t in case['traces']:
                if t['inputs']!=sorted(n for n,p in ports.items() if p['direction']=='input' and n!=case['clock']) or t['outputs']!=sorted(n for n,p in ports.items() if p['direction']=='output'):
                    raise ValueError('Trace columns do not match inspected interface')
            original=evaluate(source,dependencies,source,case,folder/'original',runner)
            if not original['discovery_pass']:
                interface=json.loads((folder/'original_inspection/interface.json').read_text())['modules'][case['top']]
                widths={n:len(v['bits']) for n,v in interface['netnames'].items() if re.fullmatch(r'[A-Za-z_]\w*',n)}
                # No fixed/corrected source or candidate outcomes enter grammar.
                pool=make_pool(source,widths)
                pool=[c for c in pool if _admissible(c['rtl'],source,ports)]
                dep=folder/'dependency';dep.mkdir();(dep/'candidate.v').write_text(source);(dep/'dependencies.v').write_text(dependencies)
                (dep/'inspect.ys').write_text(f'read_verilog -sv candidate.v dependencies.v\nhierarchy -check -top {case["top"]}\nproc\nflatten\nmemory_collect\nwrite_json flattened.json\n')
                command=runner.run('inspect',dep,case['top'])
                if command['status']!='PASS':raise RuntimeError('Original dependency extraction failed')
                module=json.loads((dep/'flattened.json').read_text())['modules'][case['top']]
                failures=original['traces'][0]['first_mismatches'] if original['traces'] else []
                cards=build_cards(source,pool,module,failures)
                for candidate,card in zip(pool,cards):
                    result=evaluate(candidate['rtl'],dependencies,source,case,folder/candidate['id'],runner)
                    labels[card['id']]={k:result[k] for k in ('accepted','discovery_pass','eda_seconds','status')}
        except (ValueError,RuntimeError,OSError,KeyError) as exc:
            error=type(exc).__name__+': '+str(exc);pool=[];cards=[];labels={}
        payload={'cards':cards,'source_order':[c['id'] for c in cards],'size_order':size_order(cards),'heuristic_order':heuristic_order(cards),
                 'original_discovery':feedback(original),'original_discovery_pass':original['discovery_pass']}
        public.append(public_packet(identity,source,dependencies,case,payload))
        private[identity]={'labels':labels,'original_accepted':original['accepted']}
        metadata[identity]={'project':item['project'],'module':item['top'],'kind':item['kind'],'solution_seeded':False,
            'exposure':spec['exposure'],'preparation_error':error,'source_sha256':sha256(source.encode()),'upstream':item.get('upstream')}
        write_json(folder/'pool.json',pool)
        print({'prepared':identity,'source_only_candidates':len(cards),'unsupported':error is not None},flush=True)
    bundle=output/'bundle'
    meta={'schema_version':1,'cohort':spec['cohort'],'exposure':spec['exposure'],'cases':metadata,
        'validation_fixture':bool(spec.get('validation_fixture')),
        'claim_scope':'finite_source_grammar_at_declared_profiles','oracle_scope':spec['oracle_scope'],
        'source_manifest_sha256':sha256(manifest_file.read_bytes()),'input_hashes':input_hashes,
        'grammar_coverage_denominator_includes_empty_and_unrepairable_pools':True,
        'tool_versions':{n:runner.version(n) for n in ('yosys','verilator','g++','make')}}
    if registration:
        from .protocol import verify_study
        verify_study(registration)
        meta.update({'study_registration':registration,'preparation_checked_registered_policy':True})
    create_bundle(bundle,public,private,meta);return bundle


def _admissible(candidate,source,ports):
    try:source_policy(candidate,source,ports);return True
    except ValueError:return False
