"""Recorded same-pool constrained search, with no-model selected-source rechecks."""
from __future__ import annotations

import io
import json
from pathlib import Path
import zipfile

import streamlit as st

from rtl_agent.common import ROOT,new_run_dir,sha256
from rtl_agent.known_bugs_v2.cases import DATA
from rtl_agent.known_bugs_v2.evaluator import evaluate,snapshot
from known_bugs_v2_app import ready,render_check
from workspace_service import execution_slot

DEMO=ROOT/'demo/repair_search'


@st.cache_data(show_spinner=False,max_entries=6)
def evidence(opaque_id,case_id):
    files={};record=DEMO/'run'/opaque_id
    for p in sorted(record.rglob('*')):
        if p.is_file() and 'obj_dir' not in p.parts and p.suffix in ('.json','.v','.cpp','.log','.patch'):
            files['record/'+str(p.relative_to(record))]=p.read_bytes()
    for folder,label in ((DATA/case_id,'sealed_case'),(DEMO/'prepared_pools'/opaque_id,'prepared_pool'),(DEMO/'run/controller_source','controller_source')):
        for p in sorted(folder.rglob('*')):
            if p.is_file() and (folder!=DEMO/'prepared_pools'/opaque_id or p.name in ('pool.json','policy_filtered.json')):
                files[label+'/'+str(p.relative_to(folder))]=p.read_bytes()
    for name in ('MODIFICATIONS.md','ARTIFACT-LICENSE-BSD-3-Clause.txt'):
        files[name]=(DEMO/name).read_bytes()
    files['study_protocol.json']=(DEMO/'run/protocol.json').read_bytes()
    manifest={name:{'sha256':sha256(data),'bytes':len(data)} for name,data in files.items()}
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
        z.writestr('manifest.json',json.dumps(manifest,indent=2))
    return buf.getvalue()


def main():
    st.set_page_config(page_title='RTLRefine · Constrained search',layout='wide')
    st.caption('RTLREFINE · GENERATED PATCHES · NVIDIA RANKS EXISTING CANDIDATES')
    st.title('Small patches. A measured role for AI.')
    path=DEMO/'run/summary.json'
    if not path.exists():
        st.info('The complete search study has not been exported yet.')
        return
    summary=json.loads(path.read_text());totals=summary['totals']
    a,b,c=st.columns(3)
    a.metric('Static-search trace passes',f"{totals['static_search']['real_trace_passes']}/9")
    b.metric('NVIDIA-prioritized trace passes',f"{totals['nvidia_prioritized']['real_trace_passes']}/9")
    c.metric('NVIDIA ranking calls',summary['unique_model_calls'])
    st.write('Both methods receive the same source-only candidate pool and at most eight candidate checks. They share two fixed starting candidates. NVIDIA can reorder later candidates, but cannot write RTL or expand the pool.')
    st.caption(f"Estimated ranking API cost ${summary['estimated_api_cost_usd']:.5f}; local compute is additional. No SMT solver was used. This is a restricted lexical edit grammar with Yosys-resolved widths.")
    st.info('Known development cases after the earlier V2 study and one retention pilot. Golden-trace agreement at fixed profiles is not unbounded correctness, held-out accuracy or proof of novelty. The older two-call V2 study used a different compute budget and is not a matched baseline here.')
    view=st.radio('Search view',['Complete comparison','Inspect a search'],horizontal=True)
    if view=='Complete comparison':
        st.table([{'Case':r['opaque_id'],'Scenario':r['case_id'],'Static':r['arms']['static_search']['status'],'NVIDIA-prioritized':r['arms']['nvidia_prioritized']['status'],
                   'Static checks':r['arms']['static_search']['logical_candidate_evaluations'],'Guided checks':r['arms']['nvidia_prioritized']['logical_candidate_evaluations']} for r in summary['cases'] if r['kind']=='historical_defect'])
        st.table([{'Method':name,'Control traces passed':f"{r['control_trace_passes']}/{r['controls']}",'Logical candidate checks':r['logical_candidate_evaluations'],
                   'Discovery passes rejected by audit':r['audit_rejected_discovery_passes']} for name,r in totals.items()])
        st.caption('Healthy inputs pass a common original-source gate, so neither method modifies them or calls the ranking model. Physical candidate checks are cached across methods. Logical tool costs are attributed to each method; they are not independent end-to-end timing measurements. Ranking adds latency and API cost.')
        with st.expander('Frozen protocol and paired outcome'):
            st.json(summary['paired_real_outcomes']);st.json(json.loads((DEMO/'run/protocol.json').read_text()))
        st.markdown('[Inspect the separate V2 code-generation comparison and oracle scope](/benchmarks)')
        return
    row=st.selectbox('Search case',summary['cases'],format_func=lambda r:r['opaque_id']+' · '+r['case_id'])
    method=st.radio('Search method',['static_search','nvidia_prioritized'],horizontal=True);arm=row['arms'][method]
    st.write('Recorded outcome: '+arm['status'])
    st.caption('Candidate pool: '+str(row['pool_candidates'])+' · logical checks: '+str(arm['logical_candidate_evaluations']))
    with st.expander('NVIDIA ranking and rationale (model explanation)'):
        st.json(row['ranking'])
    st.write('Candidate order actually tested');st.code(', '.join(arm['attempted_ids']) or 'Original source passed; no search')
    if arm['selected_source']:
        source_path=DEMO/'run'/arm['selected_source'];source=source_path.read_text()
        checked=json.loads((source_path.parent/'evaluation.json').read_text())
        render_check(checked,source_path.parent,row['opaque_id']+method)
        patch=DEMO/'run'/row['opaque_id']/(method+'.patch')
        if patch.exists():st.code(patch.read_text(),language='diff')
        if row['opaque_id']=='case_02' and method=='nvidia_prioritized':
            st.caption('Coverage limit: this selected edit changes FIFO B byte order only. These passing traces have not established the FIFO A path or all operating conditions.')
        available,why=ready()
        if not available:st.info(why)
        if st.button('Recheck selected source',disabled=not available,type='primary'):
            root=new_run_dir('constrained_search_recheck');snapshot(root)
            with st.spinner('Running the unchanged sealed V2 profiles in isolation…'):
                with execution_slot():result=evaluate(row['case_id'],source,root/'evaluation')
            st.session_state['search_recheck']={'case':row['opaque_id'],'method':method,'result':result}
        current=st.session_state.get('search_recheck')
        if current and current['case']==row['opaque_id'] and current['method']==method and current['result']['rtl_sha256']==sha256(source.encode()):
            st.subheader('Fresh recheck');render_check(current['result'],current['result']['directory'],'fresh_search_'+row['opaque_id'])
    st.download_button('Download search evidence',evidence(row['opaque_id'],row['case_id']),file_name=row['opaque_id']+'-search-evidence.zip')
    st.caption('Browsing and rechecking do not call a model. Candidate source was generated before ranking. All vendor licenses and research artifact notices remain in the export.')


if __name__=='__main__':main()
