"""Inspect machine-grounded candidate priorities and their measured limits."""
from __future__ import annotations

import difflib
import io
import json
import zipfile

import streamlit as st

from rtl_agent.common import ROOT,new_run_dir,sha256
from rtl_agent.evidence_ranking.evaluate import score_order
from rtl_agent.evidence_ranking.holdout_tools import evaluate_source
from rtl_agent.evidence_ranking.service import rank_existing_pool
from rtl_agent.known_bugs_v2.runner import BenchmarkRunner
from known_bugs_v2_app import ready
from workspace_service import execution_slot

DEMO=ROOT/'demo/evidence_ranking'
LABELS={'source_order':'Source order','size_order':'Smallest edit','heuristic_order':'Circuit evidence',
        'raw_model':'NVIDIA without evidence cards','evidence_single':'NVIDIA with evidence cards',
        'evidence_consensus':'Stability-gated NVIDIA + circuit evidence'}


def read(path):return json.loads(path.read_text())


def fill(ids,base):return list(ids)+[identity for identity in base if identity not in ids]


def orders(payload,trial):
    base=payload['heuristic_order']
    result={key:payload[key] for key in ('source_order','size_order','heuristic_order')}
    result['raw_model']=fill(trial['raw']['ids'],base) if trial['raw']['status']=='VALID' else base
    result['evidence_single']=fill(trial['views'][0]['ids'],base) if trial['views'][0]['status']=='VALID' else base
    result['evidence_consensus']=trial['consensus']['order']
    return result


@st.cache_data(show_spinner=False,max_entries=20)
def case_download(cohort,opaque,revision):
    base=DEMO/cohort;files={}
    for label in ('inputs','plans','raw_plans','catalog','pools'):
        folder=base/label/opaque
        if folder.exists():
            for p in folder.rglob('*'):
                if p.is_file():files[label+'/'+str(p.relative_to(base/label))]=p.read_bytes()
    if cohort=='holdout':
        module=read(base/'inputs'/opaque/'case.json')['module_id']
        for p in (base/'inputs'/module).rglob('*'):
            if p.is_file():files['inputs/'+str(p.relative_to(base/'inputs'))]=p.read_bytes()
        for p in (DEMO/'source_provenance/sources'/module).rglob('*'):
            if p.is_file():files['source_license/'+p.name]=p.read_bytes()
    else:
        from rtl_agent.known_bugs_v2.cases import DATA
        case_id=read(base/'inputs'/opaque/'rank_input.json')['case_id']
        for p in (DATA/case_id).rglob('*'):
            if p.is_file():files['sealed_case/'+str(p.relative_to(DATA/case_id))]=p.read_bytes()
    files['COHORTS.json']=(DEMO/'COHORTS.json').read_bytes()
    files['score_summary.json']=(base/'scores/summary.json').read_bytes()
    files['manifest.json']=json.dumps({n:sha256(data) for n,data in files.items()},indent=2).encode()
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items():archive.writestr(name,data)
    return buf.getvalue()


def portable_case(cohort,opaque):
    base=DEMO/cohort/'inputs'
    if cohort=='development':
        from rtl_agent.known_bugs_v2.cases import DATA,load
        case_id=read(base/opaque/'rank_input.json')['case_id'];case=load(case_id)
        case['traces']=[{**t,'stimulus':str(DATA/case_id/t['stimulus']),'expected':str(DATA/case_id/t['expected'])} for t in case['traces']]
        return case
    case=read(base/opaque/'case.json');module=case['module_id']
    case['traces']=[{**t,'stimulus':str(base/module/f'trace_{i}/stimulus.hex'),
                     'expected':str(base/module/f'trace_{i}/expected.hex')} for i,t in enumerate(case['traces'])]
    return case


def main():
    st.set_page_config(page_title='RTLRefine · Evidence ranking',layout='wide')
    st.caption('RTLREFINE · FAILURE OBSERVATIONS → CIRCUIT EVIDENCE → CHECK PRIORITY')
    st.title('Spend the next RTL check where the evidence points.')
    st.write('Each patch has a content ID, an observed failure, circuit dependency ranges and the exact source edit. NVIDIA can rank these IDs. A repeatability check decides whether to use its order or the fixed circuit heuristic.')
    if not (DEMO/'COHORTS.json').exists():
        st.info('The frozen ranking evaluation is running. Complete results will appear after all plans and candidate checks finish.')
        return
    cohort=st.selectbox('Evaluation cohort',['holdout','development'],format_func=lambda x:'New modules · synthetic faults' if x=='holdout' else 'Known historical development cases')
    base=DEMO/cohort;summary=read(base/'scores/summary.json');rows=[r for r in summary['cases'] if not r['original_pass']]
    totals=summary['totals'];n=len(rows);guided=totals['evidence_consensus']['accepted_per_trial']
    a,b,c=st.columns(3)
    a.metric('Circuit evidence · trace passes',f"{totals['heuristic_order']['accepted_cases']}/{n}")
    b.metric('Stability-gated order · trace passes',', '.join(str(x) for x in guided)+f' / {n}')
    c.metric('Uniform random · expected passes',f"{summary['exact_random_expected_accepted_cases']:.2f} / {n}")
    best_simple=max(totals[key]['accepted_cases'] for key in ('source_order','size_order','heuristic_order'))
    if sum(guided)/len(guided)<=best_simple:
        st.write(f'The strongest simple baseline passes {best_simple}/{n}. This study has not established an advantage over that baseline.')
    if cohort=='holdout':
        st.info('Four new-to-development modules, ten constructed faults and four normal controls. Each candidate pool is seeded with the known inverse. This measures ranking given a solution-containing pool; it does not measure bug discovery, real historical repairs or candidate-generation coverage. Public source may be in model training data.')
    else:
        st.info('These nine historical cases were already used during development. Three trials reuse the same cases. The ID-only interpretation was amended before outcome analysis after model-written source citations failed validation; original strict results remain available.')
    st.caption('Same pool and at most eight candidate checks. Stop at the first public-trace pass, then audit it once without retries. NVIDIA inference cost and latency are additional; end-to-end compute is unequal. Golden-trace agreement is bounded evidence.')
    view=st.radio('Ranking view',['Compare methods','Inspect priorities'],horizontal=True)
    if view=='Compare methods':
        table=[]
        for method,total in totals.items():
            passes=str(total['accepted_cases']) if 'accepted_cases' in total else ', '.join(map(str,total['accepted_per_trial']))
            table.append({'Method':LABELS[method],'Accepted cases per trial':passes,'Cases':n})
        st.table(table)
        st.caption('Model-format errors fall back to the circuit heuristic. Three permuted evidence views are used per consensus trial; one view is used for each single-model method. Repeatability is not a correctness probability.')
        st.table([{'Case':r['case'],'Source order':r['baselines']['source_order']['accepted'],
                   'Circuit evidence':r['baselines']['heuristic_order']['accepted'],
                   'Stability-gated passes':[t['methods']['evidence_consensus']['accepted'] for t in r['trials']],
                   'Model order used':[t['used_model_order'] for t in r['trials']],
                   'Random expected pass':round(r['exact_random']['accepted_probability'],3)} for r in rows])
        with st.expander('Scope, controls and frozen study records'):
            st.json(read(DEMO/'COHORTS.json'))
            if cohort=='holdout':st.json(read(base/'inputs/manifest.json')['modules'])
            st.json(read(base/'plans/protocol.json') if (base/'plans/protocol.json').exists() else read(base/'raw_plans/protocol.json'))
        return
    row=st.selectbox('Ranking case',rows,format_func=lambda r:r['case']+' · '+r['case_id'])
    opaque=row['case'];payload=read(base/'inputs'/opaque/'rank_input.json')
    plans=read(base/'plans'/opaque/'plans.json')
    trial_number=st.selectbox('Recorded trial',list(range(1,len(plans['trials'])+1)))
    trial=plans['trials'][trial_number-1];all_orders=orders(payload,trial)
    method=st.selectbox('Ranking method',list(LABELS),format_func=LABELS.get)
    active=st.session_state.get('fresh_rank')
    if active and active['cohort']==cohort and active['case']==opaque and method=='evidence_consensus':
        all_orders[method]=active['result']['order'];gate=active['result']
    else:gate=trial['consensus']
    order=all_orders[method];cards={c['id']:c for c in payload['cards']}
    st.write('Observed public failure')
    st.table(payload['original_discovery']['traces'][0]['first_mismatches'][:3])
    d,e,f=st.columns(3)
    d.metric('Candidate check cap','8')
    e.metric('Top-eight repeatability',f"{gate['stability']:.3f}")
    f.metric('Gate decision','Use model order' if gate['used_model_order'] else 'Use circuit heuristic')
    st.caption('Repeatability is mean pairwise Jaccard overlap of top-eight IDs across menu permutations. Threshold 0.35 was frozen before evaluation. This does not measure correctness or independently isolate position bias.')
    st.table([{'Priority':i+1,'Patch ID':identity,'Line':cards[identity]['line'],'Targets':', '.join(cards[identity]['changed_targets']),
               'Circuit score':round(cards[identity]['heuristic_score'],3),'Related-site fraction':cards[identity]['structural_coverage']['fraction']} for i,identity in enumerate(order[:8])])
    identity=st.selectbox('Inspect patch evidence',order,format_func=lambda key:f"{order.index(key)+1}. {key} · line {cards[key]['line']}")
    card=cards[identity]
    pool_file=base/('pools' if cohort=='development' else 'inputs')/opaque/'pool.json'
    pool=read(pool_file);candidate=next(p for p in pool if p['rtl_sha256']==card['rtl_sha256'])
    source=(base/'inputs'/opaque/'candidate.v').read_text()
    st.code(''.join(difflib.unified_diff(source.splitlines(True),candidate['rtl'].splitlines(True),fromfile='original.v',tofile='candidate.v')),language='diff')
    st.write('Machine-attached evidence')
    st.json({k:card[k] for k in ('id','rtl_sha256','failure_anchors','dependency','structural_coverage','changed_targets','heuristic_components')})
    st.caption('Dependency ranges are a bounded static overapproximation and can cover an entire always block. Structural bundles need not be semantically required. A source connection is not a measured causal effect.')
    with st.expander('Model mechanism hypotheses · unverified'):
        raw=base/('raw_plans' if cohort=='development' else 'plans')/opaque/f'trial_{trial_number}'
        claims=[]
        for p in sorted(raw.glob('evidence_view_*/response.json')):
            try:
                value=json.loads(read(p)['choices'][0]['message']['content'])
                claims.extend({'view':p.parent.name,**item} for item in value['ranking'] if item.get('id')==identity)
            except (ValueError,KeyError,TypeError):pass
        st.json(claims)
    labels=read(base/'catalog'/opaque/'catalog.json')['candidate_labels']
    outcomes={key:labels[c['rtl_sha256']] for key,c in cards.items()}
    if st.button('Replay recorded eight-check budget',type='primary'):
        st.session_state['rank_replay']={'cohort':cohort,'case':opaque,'method':method,'order_hash':sha256(json.dumps(order).encode()),'result':score_order(order,outcomes)}
    replay=st.session_state.get('rank_replay')
    if replay and (replay['cohort'],replay['case'],replay['method'],replay['order_hash'])==(cohort,opaque,method,sha256(json.dumps(order).encode())):
        st.write('Recorded outcome replay · no new simulation or API request')
        st.json(replay['result'])
    available,why=ready()
    if not available:st.caption(why)
    if st.button('Run fresh isolated checks on this patch',disabled=not available):
        case=portable_case(cohort,opaque);root=new_run_dir('ranking_patch_recheck')
        with st.spinner('Compiling this exact source and checking fixed public and audit traces…'):
            with execution_slot():
                if cohort=='development':
                    from rtl_agent.known_bugs_v2.evaluator import evaluate
                    result=evaluate(row['case_id'],candidate['rtl'],root/'evaluation')
                else:result=evaluate_source(candidate['rtl'],source,case,root/'evaluation',BenchmarkRunner())
        st.session_state['rank_check']={'id':identity,'cohort':cohort,'case':opaque,'result':result}
    checked=st.session_state.get('rank_check')
    if checked and (checked['id'],checked['cohort'],checked['case'])==(identity,cohort,opaque):
        result=checked['result']
        if result['accepted']:st.success('Fresh check: all three fixed traces passed.')
        else:st.warning('Fresh check: this candidate was not accepted.')
        st.caption('Checked source SHA-256: '+result['rtl_sha256'])
        with st.expander('Fresh check records'):st.json(result)
    # Owner-only live inference is deliberately separate from recorded browsing.
    import os
    if os.getenv('RTLREFINE_ENABLE_LIVE_MODEL')=='1':
        with st.expander('Fresh NVIDIA ranking · three paid views'):
            st.caption('Uses the original public failure and supplied pool. Private candidate outcomes are not sent. Three bounded calls use the persistent $50 total / $20 development guard; a full conservative reservation must fit before starting.')
            if st.button('Request three new ranking views'):
                case=portable_case(cohort,opaque);root=new_run_dir('live_evidence_rank')
                netlist=read(base/'inputs'/opaque/'flattened.json')['modules'][case['top']]
                dependencies=(base/'inputs'/opaque/'dependencies.v').read_text()
                try:
                    with st.spinner('Ranking candidate IDs on Nebius and checking repeatability…'):
                        with execution_slot():fresh=rank_existing_pool(case,source,dependencies,pool,netlist,payload['original_discovery'],root/'ranking',live=True)
                    st.session_state['fresh_rank']={'cohort':cohort,'case':opaque,'result':fresh};st.rerun()
                except (ValueError,RuntimeError,OSError) as exc:st.error(str(exc))
    st.download_button('Download case ranking evidence',case_download(cohort,opaque,sha256((DEMO/'MANIFEST.json').read_bytes())),file_name=opaque+'-ranking-evidence.zip')


if __name__=='__main__':main()
