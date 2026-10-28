"""Presentation-only repair workspace; execution and admission stay unchanged."""
from __future__ import annotations

import difflib
from html import escape
import io
import json
import os
from pathlib import Path
import zipfile

import streamlit as st

from .common import ROOT,new_run_dir,sha256
from .batch_repair.workflow import CASES,original,repair
from .known_bugs_v2.cases import DATA
from .known_bugs_v2.evaluator import evaluate
from .studio_theme import apply_theme,badge,topbar,steps,waveform
from known_bugs_v2_app import ready
from workspace_service import execution_slot

DEMO=ROOT/'demo/repair_studio'


def read(path):return json.loads(path.read_text())


@st.cache_data(show_spinner=False,max_entries=6)
def evidence_zip(folder,case_id,revision):
    root=Path(folder);files={}
    for p in root.rglob('*'):
        if p.is_file() and 'obj_dir' not in p.parts and p.suffix in ('.json','.v','.cpp','.log','.py'):
            files['run/'+str(p.relative_to(root))]=p.read_bytes()
    for p in (DATA/case_id).rglob('*'):
        if p.is_file():files['case/'+str(p.relative_to(DATA/case_id))]=p.read_bytes()
    for name in ('MODIFICATIONS.md','ARTIFACT-LICENSE-BSD-3-Clause.txt'):
        if (DEMO/name).exists():files[name]=(DEMO/name).read_bytes()
    files['manifest.json']=json.dumps({n:sha256(data) for n,data in files.items()},indent=2).encode()
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items():archive.writestr(name,data)
    return buffer.getvalue()


def resolve_record(key,source):
    current=st.session_state.get('studio_run')
    if current and current['key']==key and current['sha']==sha256(source.encode()):
        return current['result'],Path(current['folder']),'Fresh run'
    folder=DEMO/key/'run'
    if source==original(key) and (folder/'result.json').exists():
        return read(folder/'result.json'),folder,'Saved NVIDIA run'
    return None,None,'Source changed'


def checked_source(record,folder):
    if not record or not record.get('final_check') or not (folder/'selected.v').exists():return None
    source=(folder/'selected.v').read_text()
    if sha256(source.encode())!=record.get('selected_sha256'):raise ValueError('Stored patch hash changed. Run a new check.')
    return source


def restore_example(key):
    st.session_state['studio_source_'+key]=original(key)


def patch_panel(record,folder,source,patch):
    if patch is None:
        st.html('<div class="studio-empty"><strong>Your next check starts here.</strong>Edit the supported source, then run a repair.<br>Previous results are hidden when the source changes.</div>')
        return
    lines=list(difflib.unified_diff(source.splitlines(True),patch.splitlines(True),fromfile='original.v',tofile='checked_patch.v',n=2))
    added=sum(line.startswith('+') and not line.startswith('+++') for line in lines)
    removed=sum(line.startswith('-') and not line.startswith('---') for line in lines)
    st.html('<div class="studio-filebar">original.v <span>→</span> checked_patch.v<span class="studio-change-count">+'+str(added)+' / −'+str(removed)+'</span></div>')
    if lines:st.code(''.join(lines[2:]),language='diff',height=190)
    else:st.info('The source is unchanged. Its three fixed profiles were checked.')
    note=None
    pool=folder/'pool.json'
    if pool.exists():
        selected=next((p for p in read(pool) if p['id']==record.get('selected_id')),None)
        if selected:note=selected['note']
    if note:st.html('<div class="studio-change-note"><b>Source change</b> &nbsp; '+escape(note)+'.</div>')
    st.caption('The diff is the exact file used by the independent checker.')


def trace_panel(record):
    st.html('<div class="studio-section-head"><span class="studio-eyebrow">Observed output</span><span class="studio-eyebrow">PUBLIC PROFILE</span></div>')
    before=record.get('before') if record else None;after=record.get('after') if record else None
    if not before:
        st.caption('Captured signal samples appear after a completed original check.');return
    first,last=before['rows'][0]['cycle'],before['rows'][-1]['cycle']
    st.html('<div class="studio-trace-head"><span class="studio-trace-signal">'+escape(before['port'])+'</span><span class="studio-trace-cycle">cycles '+str(first)+'–'+str(last)+'</span></div>')
    st.markdown(waveform(before,after),unsafe_allow_html=True)
    st.caption('Captured after current inputs settle, before the rising edge. Shaded columns mark an original mismatch.')
    with st.expander('Inspect captured values'):
        by={r['cycle']:r for r in after['rows']} if after else {}
        st.dataframe([{'Cycle':r['cycle'],'Expected (hex)':r['expected'],'Original (hex)':r['actual'],
            'Checked (hex)':by.get(r['cycle'],{}).get('actual','—'),'Original matches':r['match'],
            'Checked matches':by.get(r['cycle'],{}).get('match')} for r in before['rows']],hide_index=True,width='stretch')
        st.caption('? marks an unqualified expected value excluded from comparison.')


def model_notes(record):
    if not record:return
    diagnosis=record.get('diagnosis')
    if diagnosis:
        with st.expander('NVIDIA hypotheses · unverified'):
            st.subheader('Nemotron diagnosis')
            if diagnosis['status']=='VALID':st.write(diagnosis['diagnosis'])
            else:st.info('The model response could not be used. Local bounded search continued; the response is retained.')
            if record.get('diagnosis_revised_after_public_checks'):
                st.caption('Revised after public candidate checks. Private audits were unavailable when selecting the patch.')
            st.caption('Model prose is a hypothesis. Acceptance comes from independently running the exact patch.')
            if record.get('initial_diagnosis'):
                st.markdown('**Initial hypothesis, before public check feedback**')
                st.write(record['initial_diagnosis'].get('diagnosis') or record['initial_diagnosis'].get('error'))


def profile_rows(checked):
    traces=checked.get('traces',[]) if checked else [];rows=[]
    for i,label in enumerate(('Public regression','Additional profile 01','Additional profile 02')):
        trace=traces[i] if i<len(traces) else None
        if trace is None or trace.get('command',{}).get('status') not in (None,'PASS'):state,kind='Not completed','waiting'
        elif trace['passed']:state,kind='Passed','passed'
        else:state,kind='Failed','failed'
        rows.append('<div class="studio-profile"><span>'+label+'</span><span class="'+kind+'">'+state+'</span></div>')
    return '<div class="studio-profile-list">'+''.join(rows)+'</div>'


def receipt(record,folder,patch,available,why,origin):
    checked=record.get('final_check') if record else None
    accepted=bool(record and patch is not None and record.get('accepted'))
    label='Accepted' if accepted else 'Not accepted' if checked else 'Awaiting check'
    kind='good' if accepted else 'bad' if checked else 'pending'
    st.html('<div class="studio-section-head"><span class="studio-eyebrow">Verification receipt</span>'+badge(label,kind)+'</div>')
    count=sum(t.get('passed',False) for t in checked.get('traces',[])) if checked else 0
    st.metric('Independent profiles',f'{count}/3' if checked else '—')
    st.html(profile_rows(checked))
    if record:
        st.html('<div class="studio-run-stats"><div class="studio-run-stat"><label>Hypotheses</label><strong>'+str(record.get('pool_candidates','—'))+'</strong></div><div class="studio-run-stat"><label>NVIDIA calls</label><strong>'+str(record.get('api_requests',0))+'</strong></div><div class="studio-run-stat"><label>'+('Recorded time' if origin.startswith('Saved') else 'Run time')+'</label><strong>'+f"{record.get('wall_seconds',0):.1f}s"+'</strong></div></div>')
    if record and record.get('error'):st.error(record['error'])
    if checked:
        if any(t.get('command',{}).get('status') not in (None,'PASS') for t in checked['traces']):
            st.error('A native worker did not finish. Inspect its execution logs before drawing a conclusion about the source.')
        if accepted and record.get('original_public_profile_already_passed'):st.success('Your unchanged source passed all three fixed profiles. No repair was needed within this scope.')
        elif accepted:st.success('The exact patch passed all three fixed profiles.')
        else:st.warning('The selected patch failed independent checks and was not accepted.')
    if patch is not None:
        identity=record['selected_sha256']
        st.html('<div class="studio-source-hash">SOURCE SHA-256<br><b>'+identity[:24]+'…'+identity[-12:]+'</b></div>')
        if accepted:st.download_button('Download checked RTL',patch,file_name=CASES[record['key']]['case_id']+'-checked.v',mime='text/plain',type='primary',width='stretch')
        if st.button('Recheck this exact patch',disabled=not available,key='studio_recheck',width='stretch'):
            root=new_run_dir('studio_patch_recheck')
            with st.spinner('Running the exact source on three fixed profiles…'):
                with execution_slot():result=evaluate(record['case_id'],patch,root/'evaluation')
            st.session_state['studio_checked']={'sha':identity,'result':result}
        fresh=st.session_state.get('studio_checked')
        if fresh and fresh['sha']==identity:
            if fresh['result']['accepted']:st.success('Fresh recheck passed · exact source hash verified.')
            else:st.warning('Fresh recheck did not accept this patch.')
        st.download_button('Download verification evidence',evidence_zip(str(folder),record['case_id'],sha256((folder/'result.json').read_bytes())),file_name=record['key']+'-repair-evidence.zip',width='stretch')
    if record and checked:
        with st.expander('Verification scope & run details'):
            st.write(record['scope'])
            st.write('Three fixed two-state, valid-qualified golden-trace profiles. Frame-length expectations also have an independent byte-count guard. This is bounded evidence, not arbitrary-RTL or unbounded correctness.')
            st.write('Source-generated candidates are screened with shared compilation. The selected uninstrumented source is independently rebuilt. Failed private audits never grant another selection.')
            st.caption('Source SHA-256: '+record.get('selected_sha256','—'))
            if (folder/'events.json').exists():st.table(read(folder/'events.json'))
            if record.get('diagnosis'):st.json(record['diagnosis'])
            if not record.get('accepted'):
                mismatches=[{'Profile':t.get('trace_label',''),'Cycle':m['cycle'],'Output':m['port'],'Expected':hex(m['expected']),'Observed':hex(m['actual'])}
                    for t in checked['traces'] for m in t.get('first_mismatches',[])[:2]]
                if mismatches:st.table(mismatches)
    st.caption('Fixed profiles · isolated native tools · no FPGA board required.')
    if not available:st.caption(why)


def render_studio():
    st.set_page_config(page_title='RTLRefine · Repair studio',layout='wide',initial_sidebar_state='collapsed')
    apply_theme()
    with st.container(key='studio_shell'):
        topbar()
        measured=read(DEMO/'throughput/summary.json') if (DEMO/'throughput/summary.json').exists() else None
        hero_left,hero_right=st.columns([2.05,1],gap='medium')
        with hero_left:
            st.title('An AI fix needs evidence.')
            st.html('<p class="studio-intro-copy">Inspect the failure. Review the change. Keep the exact source<br>only after its independent checks pass.</p>')
            st.page_link('project_app.py',label='Open your own RTL project',icon=':material/folder_open:')
            st.page_link('property_app.py',label='Find FIFO failures beyond a passing test',icon=':material/fact_check:')
            st.page_link('external_validation_app.py',label='Inspect real external RTL validation',icon=':material/verified:')
        with hero_right:
            if measured:st.html('<div class="studio-performance"><strong>'+f"{measured['speedup']:.1f}×"+'</strong>measured screening throughput<br>'+str(measured['total_candidates'])+' hypotheses · '+str(len(measured['cases']))+' profiles</div>')
        step_slot=st.empty()
        with st.container(key='studio_workspace'):
            left,right=st.columns([2.05,1],gap='medium')
            with left:
                with st.container(key='studio_case'):
                    key=st.selectbox('Choose a real RTL failure',tuple(CASES),format_func=lambda k:CASES[k]['title'])
                    st.html('<div class="studio-case-description">'+escape(CASES[key]['problem'])+'</div>')
                with st.container(key='studio_editor'):
                    module=read(DATA/CASES[key]['case_id']/'case.json')['edited_module']
                    editor_head=st.empty()
                    review_tab,original_tab,edit_tab=st.tabs(['Patch review','Original RTL','Edit source'])
                    with edit_tab:
                        st.caption('Preserve the license/header, ports, parameters and clock. Editing requires new checks.')
                        source=st.text_area('RTL source',original(key),height=330,key='studio_source_'+key,label_visibility='collapsed')
                        st.button('Restore example',key='studio_restore_'+key,on_click=restore_example,args=(key,),type='tertiary')
                trace_slot=st.container(key='studio_trace');notes_slot=st.container()
            with right:
                available,why=ready();owner_live=os.getenv('RTLREFINE_ENABLE_LIVE_MODEL')=='1'
                with st.container(key='studio_actions'):
                    st.html('<div class="studio-section-head"><span class="studio-eyebrow">New run</span>'+badge('Live enabled' if owner_live and available else 'Saved examples','good' if owner_live and available else 'saved')+'</div>')
                    live=st.button('Diagnose and repair with NVIDIA',type='primary',disabled=not (available and owner_live),width='stretch')
                    local=st.button('Run bounded local search',disabled=not available,width='stretch')
                    st.caption('Live diagnosis: up to 2 paid requests.' if owner_live else 'New model calls are disabled. Saved runs and native rechecks remain available.')
                receipt_slot=st.container(key='studio_receipt')
            if live or local:
                try:
                    with st.status('Reproducing and repairing…',expanded=True) as status:
                        with execution_slot():result=repair(key,source,live=live,on_event=lambda e:st.write(e['message']))
                        status.update(label='Patch checked' if result['accepted'] else 'Search finished; inspect the outcome',state='complete')
                    st.session_state['studio_run']={'key':key,'sha':sha256(source.encode()),'result':result,'folder':result['directory']}
                except (ValueError,RuntimeError,OSError,KeyError) as exc:st.error(str(exc))
            record,folder,origin=resolve_record(key,source)
            try:patch=checked_source(record,folder)
            except ValueError as exc:st.error(str(exc));record=None;folder=None;patch=None
            with step_slot.container():steps(record)
            with editor_head.container():
                st.html('<div class="studio-section-head"><span class="studio-eyebrow">'+escape(module)+'.v</span>'+badge('Saved NVIDIA run' if record and origin.startswith('Saved') else 'Fresh run' if record else 'Source changed','saved' if record else 'pending')+'</div>')
            with review_tab:
                patch_panel(record,folder,source,patch)
            with original_tab:st.code(source,language='verilog',line_numbers=True,height=330)
            with trace_slot:trace_panel(record)
            with notes_slot:model_notes(record)
            with receipt_slot:receipt(record,folder,patch,available,why,origin)
        if measured:
            with st.expander('Screening benchmark · measurement & scope'):
                st.metric('Measured complete-pool screening throughput',f"{measured['speedup']:.1f}×")
                st.write(f"The same {measured['total_candidates']} candidates across three historical profiles: {measured['serial_seconds']:.1f}s with separate compilation, {measured['batch_seconds']:.1f}s with sharing. Every screening result matched, including compatibility fallbacks and the inactive-output control.")
                st.caption('One paired fresh-build-directory measurement per case on this host; filesystem caches were not flushed. Screening throughput is not end-to-end repair speed, unseen accuracy or unbounded equivalence.')
        st.html('<div class="studio-footer"><span>RTLRefine / checks you can reproduce</span><span>NVIDIA Nemotron on Nebius · finite repair scope</span></div>')
