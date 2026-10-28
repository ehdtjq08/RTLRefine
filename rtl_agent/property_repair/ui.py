"""A product view of independently found failures and the exact checked patch."""
import difflib
import json
import os
from pathlib import Path

import streamlit as st

from ..common import ROOT,sha256,new_run_dir
from ..studio_theme import apply_theme,topbar
from ..tool_paths import find_tool
from ..project_repair.project import load_project,read_archive,archive_project
from ..project_repair.ui import evidence,wizard
from .examples import example_files
from .contract import load_contract,bind_contract,TEXT,contract_id
from .workflow import run_repair
from .regressions import inherited_cases,public_case,contract_sequence,merge_cases,with_bundle,check_bundle
from .setup_ui import configure_contract
from .source_ui import source_editor
from workspace_service import execution_slot

DEMO=ROOT/'demo/functional_repair'
TITLES={'simultaneous':'Simultaneous transfers change occupancy','wrap':'Read pointer wraps too early','reset':'Reset retains stale read position','healthy':'Healthy FIFO control'}


def portable_action(blob,*,expected_failure=False):
    cache='portable_original' if expected_failure else 'portable_selected';anchor=sha256(blob)
    label='Run original failing regressions' if expected_failure else 'Run standalone regressions without NVIDIA'
    if st.button(label,width='stretch'):
        try:
            p=load_project(read_archive(blob))
            if 'rtlrefine_regressions/manifest.json' not in p.files:raise ValueError('Recheck this older export first to add portable regressions')
            with st.status('Running the bundled script in isolated Python…',expanded=False) as status:
                with execution_slot():result=check_bundle(p,new_run_dir('standalone_regressions')/'run',standalone=True)
                status.update(label='Standalone run finished',state='complete')
            st.session_state[cache]={'anchor':anchor,'result':result}
        except (ValueError,RuntimeError,OSError) as exc:st.error(str(exc))
    current=st.session_state.get(cache)
    if current and current['anchor']==anchor:
        r=current['result'];code=r.get('standalone_exit_code','—')
        passed=sum(t['passed'] for t in r.get('tests',[]));total=len(r.get('tests',[]))
        if expected_failure and r['status']=='REGRESSION_FAILED':st.warning(f'Original bug reproduced · exit {code} · {total-passed} failing regression cases. Zero model calls.')
        elif r['accepted']:st.success(f'Standalone regressions passed · exit {code} · {passed}/{total} cases. Zero model calls.')
        else:st.error('Standalone run was not accepted: '+r['status'])
        with st.expander('Standalone regression result'):
            st.json(r)


def receipt(project,c,result,folder):
    st.subheader('Independent verification')
    original=result.get('original_properties',{});smoke=result.get('original_smoke',{})
    a,b,d=st.columns(3)
    a.metric('Original smoke test','—' if 'accepted' not in smoke else 'PASS' if smoke['accepted'] else 'FAIL')
    b.metric('Original property check',str(original.get('steps','—'))+' steps' if original.get('status')=='COUNTEREXAMPLE' else original.get('status','—'))
    d.metric('NVIDIA requests',result.get('api_requests',0))
    if result['accepted']:st.success('The exact project passed tests, bounded properties and progress checks.')
    else:st.warning('No checked export: '+result.get('status','UNKNOWN'))
    if result.get('error'):st.error(result['error'])
    source_failures=[t for t in smoke.get('tests',[]) if not t['passed'] and t['status']!='ASSERTION_FAILED']
    if source_failures:
        with st.expander('Original compilation or setup diagnostics',expanded=True):
            for test in source_failures:st.code(test.get('log_tail') or test.get('error') or test['status'],language='text')
    if result.get('attempts'):
        with st.expander('Repair attempts and compiler feedback'):
            for attempt in result['attempts']:
                st.markdown('**Attempt '+str(attempt['number'])+' · '+attempt['status']+'**')
                for test in attempt.get('public_smoke',{}).get('tests',[]):
                    if not test['passed']:st.code(test.get('log_tail') or test.get('error') or test['status'],language='text')
                if attempt.get('property_error'):st.code(attempt['property_error'],language='text')
                if attempt.get('error'):st.write(attempt['error'])
                if attempt.get('proposal',{}).get('diagnosis'):st.caption('Unverified model hypothesis: '+attempt['proposal']['diagnosis'])
    original_regressions=result.get('original_regressions')
    if original_regressions and not original_regressions['accepted']:
        st.markdown('**Original source: executable regressions fail**')
        with st.expander('Reproduced regression failures'):
            for test in original_regressions.get('tests',[]):
                if not test['passed']:
                    st.caption(test['origin']+' · '+str(test['steps'])+' input steps')
                    st.code((test.get('simulation') or test['compile'])['log_tail'],language='text')
        reproduction=folder/'reproduction-project.zip'
        if reproduction.exists() and sha256(reproduction.read_bytes())==result.get('reproduction_archive_sha256'):
            st.download_button('Download failing reproduction and tests',reproduction.read_bytes(),file_name='failing-regression-project.zip',on_click='ignore')
            st.caption('This is the original failing design, not an accepted patch. Its standalone regression command should fail until the design is repaired.')
            portable_action(reproduction.read_bytes(),expected_failure=True)
    replay=original.get('replay',{})
    if replay:
        label='Shortest reproduced counterexample' if original.get('minimal_counterexample_confirmed') else 'Reproduced counterexample'
        st.markdown('**'+label+'** · '+replay['status'])
        st.dataframe([{'Step':r['cycle']+1,'Reset':r['rst'],'In valid':r['s_valid'],'In ready':r['s_ready'],'In data':r['s_data'],
                       'Out ready':r['m_ready'],'Out valid':r['m_valid'],'Out data':r['m_data'],'Expected occupancy':r['expected_count'],
                       'Violation':', '.join(r['violations'])} for r in replay['observations']],hide_index=True,width='stretch')
        st.caption('SAT input sequence replayed in Icarus against a separate Python transaction queue. No corrected FIFO RTL is used.')
    for name,new in result.get('changes',{}).items():
        st.caption(name)
        st.code(''.join(difflib.unified_diff(project.files[name].decode().splitlines(True),new.splitlines(True),fromfile=name,tofile=name)),language='diff')
    if result.get('property_audits'):
        st.table([{'Final bound':a['steps'],'Result':a['status'],'Progress':a.get('progress',{}).get('status','Checked at deepest bound')} for a in result['property_audits']])
    if result.get('final_regressions'):
        st.markdown('**Portable regression verification'+(' · included in the checked export' if result['accepted'] else '')+'**')
        st.table([{'Origin':t['origin'],'Steps':t['steps'],'Checks':t['expected_checks'],'Status':'PASS' if t['passed'] else 'FAIL'} for t in result['final_regressions'].get('tests',[])])
        st.code('python3 -I rtlrefine_regressions/run.py --report regression-report.json',language='bash')
        st.caption('Runs outside this app with Python, Icarus, bubblewrap and prlimit. No API key or Yosys is needed. Source edits are compiled afresh; changed test/oracle files are rejected.')
    elif result['accepted']:
        st.info('This saved record predates portable regression exports. Recheck it below to generate a current export with retained public counterexamples.')
    resources=result.get('resource_comparison')
    if resources:
        with st.expander('Mapped resource comparison · synthesis estimate'):
            if resources['status']=='AVAILABLE':
                names={'logic_lut_cells':'Logic LUT cells','flip_flop_cells':'Flip-flop cells','lutram_primitive_cells':'LUTRAM primitives',
                       'srl_primitive_cells':'SRL primitives','bram18_primitive_cells':'BRAM18 primitives','bram36_primitive_cells':'BRAM36 primitives','dsp_primitive_cells':'DSP primitives'}
                st.table([{'Resource':name,'Original':resources['before']['counts'][key],'Selected':resources['after']['counts'][key],'Change':resources['delta'][key]} for key,name in names.items()])
                st.caption('Xilinx 7-series mapped cells with identical settings. Logic LUT counts exclude the separately listed memory/SRL primitives. No placement, routing, timing, power or board result is implied.')
            else:st.info('Resource mapping was unavailable. Correctness checks remain separate; see evidence logs.')
    archive=folder/'checked-project.zip'
    if result['accepted'] and archive.exists():
        blob=archive.read_bytes()
        if sha256(blob)!=result.get('checked_archive_sha256'):st.error('Checked archive changed. Recheck the exact project.')
        else:
            st.download_button('Download property-checked project',blob,file_name='property-checked-project.zip',type='primary',on_click='ignore')
            portable_action(blob)
            if st.button('Recheck exported project without NVIDIA',width='stretch'):
                try:
                    with st.status('Rebuilding the exported source and running final checks…',expanded=True) as status:
                        exported=load_project(read_archive(blob))
                        cases=merge_cases(inherited_cases(exported,c),[public_case(original)],[contract_sequence(c)])
                        exported=with_bundle(exported,c,cases)
                        with execution_slot():rechecked=run_repair(exported,on_event=lambda e:st.write(e['message']))
                        status.update(label='Fresh export recheck passed' if rechecked['accepted'] else 'Fresh export recheck rejected',state='complete')
                    st.session_state['property_rechecked_export']={'anchor':sha256(blob)+contract_id(c),'result':rechecked}
                except (ValueError,RuntimeError,OSError,KeyError) as exc:st.error('Export recheck could not complete: '+str(exc))
            checked=st.session_state.get('property_rechecked_export')
            if checked and checked['anchor']==sha256(blob)+contract_id(c):
                rechecked=checked['result']
                if rechecked['accepted']:
                    current=(Path(rechecked['directory'])/'checked-project.zip').read_bytes()
                    if sha256(current)==rechecked['checked_archive_sha256']:
                        st.success('Exported ZIP passed a fresh independent recheck. Zero model requests.')
                        st.download_button('Download freshly rechecked project',current,file_name='rechecked-project.zip',on_click='ignore')
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
            if upload:
                uploaded=upload.getvalue();files=read_archive(uploaded)
                if 'rtlrefine.json' in files:project=load_project(files)
                else:
                    config=wizard(files,'fifo_project_'+sha256(uploaded)[:16])
                    if config is None:return
                    project=load_project(files,config)
                use_form=st.checkbox('Configure FIFO contract from inspected ports',value='fifo_contract.json' not in files,key='fifo_use_form_'+project.identity[:12])
            else:project=load_project(example_files(case));use_form=False
            project=source_editor(project)
            if use_form:
                c=configure_contract(project)
                if c is None:return
            else:
                c=load_contract(project)
                with st.expander('Independent FIFO contract · fixed before the run'):
                    st.write(TEXT)
                    raw=st.text_area('Contract JSON',json.dumps(c,indent=2),height=280,key='fifo_contract_'+project.identity[:12])
                    c=load_contract(project,json.loads(raw))
            project=bind_contract(project,c)
        except (ValueError,KeyError,TypeError) as exc:st.error(str(exc));return
        st.caption('DUT: '+project.config['dut_top']+' · '+str(c['data_width'])+'-bit data · capacity '+str(c['depth'])+' · public bound '+str(c['discovery_steps']))
        missing=[t for t in ['yosys','iverilog','vvp','bwrap','prlimit'] if not find_tool(t)]
        owner=os.getenv('RTLREFINE_ENABLE_LIVE_MODEL')=='1';a,b=st.columns(2)
        check=a.button('Find hidden failures without NVIDIA',type='primary',disabled=bool(missing),width='stretch')
        repair=b.button('Repair from a counterexample with NVIDIA',disabled=bool(missing) or not owner,width='stretch')
        st.caption('Checking is free of model requests. A repair uses at most two bounded requests. Public counterexamples guide repair; final audit failure is terminal.')
        if missing:st.info('Native tools required: '+', '.join(missing))
        saved=DEMO/case/'run'
        if not upload and (saved/'result.json').exists():
            saved_record=json.loads((saved/'result.json').read_text())
            if saved_record['project_id']==project.identity and saved_record['contract_id']==contract_id(c):
                if st.button('Show saved repair and evidence',type='tertiary'):
                    st.session_state.pop('property_result',None);st.rerun()
        if check or repair:
            try:
                with st.status('Checking the independent contract…',expanded=True) as status:
                    with execution_slot():result=run_repair(project,contract=c,repair=repair,on_event=lambda e:st.write(e['message']))
                    status.update(label='Verification complete',state='complete')
                st.session_state['property_result']=result
            except (ValueError,RuntimeError,OSError) as exc:st.error(str(exc))
        result=st.session_state.get('property_result');origin='Fresh run';folder=None
        if result and (result['project_id']!=project.identity or result['contract_id']!=contract_id(c)):result=None
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
