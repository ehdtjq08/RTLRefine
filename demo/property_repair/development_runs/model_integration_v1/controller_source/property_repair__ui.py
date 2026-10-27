"""A product view of independently found failures and the exact checked patch."""
import difflib
import io
import json
import os
from pathlib import Path
import zipfile

import streamlit as st

from ..common import ROOT,sha256
from ..studio_theme import apply_theme,topbar,badge
from ..tool_paths import find_tool
from ..project_repair.project import load_project,read_archive,archive_project
from ..project_repair.ui import evidence
from .examples import example_files
from .contract import load_contract,bind_contract,TEXT,contract_id
from .workflow import run_repair
from workspace_service import execution_slot

DEMO=ROOT/'demo/property_repair'
TITLES={'simultaneous':'Simultaneous transfers change occupancy','wrap':'Read pointer wraps too early','reset':'Reset retains stale read position','healthy':'Healthy FIFO control'}


def receipt(project,c,result,folder):
    st.subheader('Independent verification')
    original=result.get('original_properties',{});smoke=result.get('original_smoke',{})
    a,b,d=st.columns(3)
    a.metric('Original smoke test','PASS' if smoke.get('accepted') else 'FAIL')
    b.metric('Original property check',str(original.get('steps','—'))+' clocks' if original.get('status')=='COUNTEREXAMPLE' else original.get('status','—'))
    d.metric('NVIDIA requests',result.get('api_requests',0))
    if result['accepted']:st.success('The exact project passed tests, bounded properties and progress checks.')
    else:st.warning('No checked export: '+result.get('status','UNKNOWN'))
    replay=original.get('replay',{})
    if replay:
        label='Shortest reproduced counterexample' if original.get('minimal_counterexample_confirmed') else 'Reproduced counterexample'
        st.markdown('**'+label+'** · '+replay['status'])
        st.dataframe([{'Clock':r['cycle']+1,'Reset':r['rst'],'In valid':r['s_valid'],'In ready':r['s_ready'],'In data':r['s_data'],
                       'Out ready':r['m_ready'],'Out valid':r['m_valid'],'Out data':r['m_data'],'Expected occupancy':r['expected_count'],
                       'Violation':', '.join(r['violations'])} for r in replay['observations']],hide_index=True,width='stretch')
        st.caption('SAT input sequence replayed in Icarus against a separate Python transaction queue. No corrected FIFO RTL is used.')
    for name,new in result.get('changes',{}).items():
        st.caption(name)
        st.code(''.join(difflib.unified_diff(project.files[name].decode().splitlines(True),new.splitlines(True),fromfile=name,tofile=name)),language='diff')
    if result.get('property_audits'):
        st.table([{'Final bound':a['steps'],'Result':a['status'],'Progress':a.get('progress',{}).get('status','Checked at deepest bound')} for a in result['property_audits']])
    archive=folder/'checked-project.zip'
    if result['accepted'] and archive.exists():
        blob=archive.read_bytes()
        if sha256(blob)!=result.get('checked_archive_sha256'):st.error('Checked archive changed. Recheck the exact project.')
        else:
            st.download_button('Download property-checked project',blob,file_name='property-checked-project.zip',type='primary',on_click='ignore')
            if st.button('Recheck exported project without NVIDIA',width='stretch'):
                with st.status('Rebuilding the exported source and running final checks…',expanded=True) as status:
                    exported=load_project(read_archive(blob))
                    with execution_slot():rechecked=run_repair(exported,on_event=lambda e:st.write(e['message']))
                    status.update(label='Fresh export recheck passed' if rechecked['accepted'] else 'Fresh export recheck rejected',state='complete')
                if rechecked['accepted']:st.success('Exported ZIP passed a fresh independent recheck. Zero model requests.')
                else:st.error('Exported ZIP was not accepted: '+rechecked['status'])
    st.download_button('Download property evidence',evidence(folder),file_name='property-verification-evidence.zip',on_click='ignore')
    with st.expander('Model hypothesis and raw verification records'):
        if result.get('diagnosis'):st.write(result['diagnosis'])
        st.json({k:v for k,v in result.items() if k not in {'changes','attempts','original_properties','original_smoke'}})
    st.caption('Bounded, two-state, single-clock FIFO contract at the declared widths and capacity. This does not establish unbounded correctness, physical CDC or support for every FIFO protocol. The 15× screening measurement does not apply.')


def render_properties():
    st.set_page_config(page_title='RTLRefine · Independent properties',layout='wide',initial_sidebar_state='collapsed');apply_theme()
    with st.container(key='studio_shell'):
        topbar();st.title('A passing test can still miss a bug.')
        st.write('Find an independent FIFO counterexample, replay it in another simulator, then give NVIDIA the reproduced failure. Export only after the exact patch passes the final checks.')
        st.markdown('<a href="/" target="_self">← Repair workspace</a>',unsafe_allow_html=True)
        case=st.selectbox('Authored FIFO integration example',list(TITLES),format_func=TITLES.get)
        st.caption('These are intentionally constructed defects and a healthy control. They demonstrate this verification flow; they do not establish repair accuracy on unseen projects.')
        upload=st.file_uploader('Or upload your FIFO project ZIP',type=['zip'])
        try:
            project=load_project(read_archive(upload.getvalue())) if upload else load_project(example_files(case))
            c=load_contract(project)
            with st.expander('Independent FIFO contract · fixed before the run'):
                st.write(TEXT)
                raw=st.text_area('Contract JSON',json.dumps(c,indent=2),height=280,key='fifo_contract_'+project.identity[:12])
                c=load_contract(project,json.loads(raw))
            project=bind_contract(project,c)
        except (ValueError,KeyError,TypeError) as exc:st.error(str(exc));return
        st.caption('DUT: '+project.config['dut_top']+' · '+str(c['data_width'])+'-bit data · capacity '+str(c['depth'])+' · public bound '+str(c['discovery_steps']))
        with st.expander('Original design source'):
            for path,text in project.editable.items():st.caption(path);st.code(text,language='verilog',line_numbers=True)
        missing=[t for t in ['yosys','iverilog','vvp','bwrap','prlimit'] if not find_tool(t)]
        owner=os.getenv('RTLREFINE_ENABLE_LIVE_MODEL')=='1';a,b=st.columns(2)
        check=a.button('Find hidden failures without NVIDIA',type='primary',disabled=bool(missing),width='stretch')
        repair=b.button('Repair from a counterexample with NVIDIA',disabled=bool(missing) or not owner,width='stretch')
        st.caption('Checking is free of model requests. A repair uses at most two bounded requests. Public counterexamples guide repair; final audit failure is terminal.')
        if missing:st.info('Native tools required: '+', '.join(missing))
        if check or repair:
            try:
                with st.status('Checking the independent contract…',expanded=True) as status:
                    with execution_slot():result=run_repair(project,contract=c,repair=repair,on_event=lambda e:st.write(e['message']))
                    status.update(label='Verification complete',state='complete')
                st.session_state['property_result']=result
            except (ValueError,RuntimeError,OSError) as exc:st.error(str(exc))
        result=st.session_state.get('property_result');origin='Fresh run';folder=None
        if result and (result['project_id']!=project.identity or result['contract_id']!=contract_id(c)):result=None
        saved=DEMO/case/'run'
        if result:folder=Path(result['directory'])
        elif not upload and (saved/'result.json').exists():
            record=json.loads((saved/'result.json').read_text())
            if record['project_id']==project.identity and record['contract_id']==contract_id(c):
                result=record;folder=saved;origin='Saved actual NVIDIA run' if record['api_requests'] else 'Saved native check'
        if result:
            st.caption(origin)
            receipt(project,c,result,folder)
        else:st.info('Run the independent check to see whether the current source hides a failure.')
        st.download_button('Download current input project',archive_project(project),file_name='fifo-input.zip',on_click='ignore')
