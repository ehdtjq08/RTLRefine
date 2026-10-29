"""Upload a real project; no built-in module contract is selected here."""
from __future__ import annotations

import difflib
from html import escape
import io
import json
import os
import posixpath
import re
from pathlib import Path
import zipfile

import streamlit as st

from ..common import ROOT,sha256
from ..studio_theme import apply_theme,topbar,badge
from ..tool_paths import find_tool
from .project import read_archive,load_project
from .policy import tokens
from .examples import example_zip
from .workflow import run_project
from workspace_service import execution_slot


def modules(files,paths):
    result=[]
    for p in paths:
        ts=[t[0] for t in tokens(files[p].decode('utf-8'))]
        for i,t in enumerate(ts[:-1]):
            if t=='module':
                j=i+1
                if ts[j] in ('automatic','static'):j+=1
                if j<len(ts):result.append(ts[j])
    return list(dict.fromkeys(result))


def referenced_headers(files,paths):
    found=set();queue=list(paths)
    while queue:
        path=queue.pop()
        for name in re.findall(r'^\s*`include\s+"([^"\n]+)"',files[path].decode(),re.M):
            if name=='rtlrefine_check.vh':continue
            candidates=[posixpath.normpath(str(Path(path).parent/name)),posixpath.normpath(name)]
            chosen=next((p for p in candidates if p in files),None)
            if chosen and chosen not in found:found.add(chosen);queue.append(chosen)
    return sorted(found)


def likely_testbench(path,source):
    parts=Path(path).parts
    if any(p.lower() in {'tb','test','tests','testbench','testbenches','sim','simulation'} for p in parts[:-1]):return True
    name=Path(path).stem.lower()
    if re.search(r'(?:^|[_-])(?:tb|test|bench)(?:$|[_-])',name) or 'testbench' in name:return True
    return any(n.lower()=='tb' or n.lower().startswith(('tb_','test_')) or n.lower().endswith('_tb') for n in modules({path:source},[path]))


def completion_options(text):
    ts=tokens(text);words=[t[0] for t in ts];has_macro=False;markers=[]
    for i,word in enumerate(words):
        if words[i:i+3]==['`','RTLREFINE_DONE','(']:has_macro=True
        if word not in ('$display','$write') or i+3>=len(ts):continue
        if words[i+1]!='(' or ts[i+2][3]!='string' or words[i+3]!=')':continue
        value=words[i+2][1:-1]
        if not 1<=len(value)<=100 or any(c in value for c in '\n\r"\\%'):continue
        if re.search(r'(?:^|[\W_])(?:FAIL|FAILED|ERROR|NOT)(?:$|[\W_])',value,re.I):continue
        if re.search(r'(?:^|[\W_])(?:PASS|PASSED|SUCCESS|SUCCEEDED|DONE|COMPLETE|COMPLETED)(?:$|[\W_])',value,re.I):markers.append(value)
    return has_macro,list(dict.fromkeys(markers))


def completion_field(files,paths,label,key):
    text='\n'.join(files[p].decode() for p in paths)
    macro,options=completion_options(text)
    if macro:return None
    value=options[0] if len(options)==1 else 'PASS'
    marker=st.text_input(label,value=value,key=key,
        help='Exact one-argument $display/$write text executed only after the assertions pass. A clean $finish alone is insufficient.')
    if len(options)==1:st.caption('Suggested from an existing literal in the supplied bench; review it. No assertion or completion call is inserted.')
    elif options:st.caption('Possible existing completion literals: '+', '.join(options))
    return marker


def wizard(files,identity):
    hdl=[p for p in sorted(files) if Path(p).suffix in ('.v','.sv')]
    default=[p for p in hdl if not likely_testbench(p,files[p])]
    st.caption('File roles are suggested from paths and module names. Review the RTL list and choose the benches you want to run.')
    name=st.text_input('Project name',value='My RTL project',key=identity+'name')
    rtl=st.multiselect('RTL files (compile order)',hdl,default=default,key=identity+'rtl')
    if not rtl:st.info('Choose the design files before selecting its top module.');return None
    top_options=modules(files,rtl)
    if not top_options:st.error('No supported module declarations were found in the selected files.');return None
    top=st.selectbox('DUT top module',top_options,key=identity+'top')
    editable=st.multiselect('Files NVIDIA may edit',rtl,default=rtl[:12],key=identity+'editable')
    candidates=sorted([p for p in hdl if p not in rtl],key=lambda p:('audit' in p.lower() or 'stress' in p.lower(),'public' not in p.lower(),p))
    if not candidates:st.error('No testbench file remains outside the RTL list. Remove bench files from that list, or include a self-checking bench in the ZIP.');return None
    public=st.selectbox('Public testbench file',candidates,key=identity+'public')
    test_tops=modules(files,[public])
    if not test_tops:st.error('The testbench file has no top module.');return None
    tb=st.selectbox('Public testbench top',test_tops,key=identity+'tb')
    with st.expander('Preview the selected public testbench'):
        st.code(files[public].decode(),language='verilog')
    marker=completion_field(files,[public]+referenced_headers(files,[public]),'Success text printed only after all public checks pass',identity+'marker')
    headers=referenced_headers(files,rtl)
    tests=[{'id':'public','top':tb,'files':[public],'include_files':[p for p in referenced_headers(files,[public]) if p not in headers],
        'phase':'public','success_marker':marker}]
    audit=st.multiselect('Additional testbenches withheld from the model (optional)',[p for p in candidates if p!=public],key=identity+'audits')
    for index,path in enumerate(audit):
        choices=modules(files,[path])
        if not choices:st.error('No testbench top in '+path);return None
        audit_top=st.selectbox('Additional top: '+path,choices,key=identity+f'audit_top_{index}')
        audit_marker=completion_field(files,[path]+referenced_headers(files,[path]),'Additional success text: '+path,identity+f'audit_marker_{index}')
        tests.append({'id':f'audit_{index+1}','top':audit_top,'files':[path],
            'include_files':[p for p in referenced_headers(files,[path]) if p not in headers],'phase':'audit','success_marker':audit_marker})
    dirs=sorted({str(Path(p).parent) for p in headers+[p for t in tests for p in t['include_files']]})
    contract=st.text_area('Intended behavior (optional)',height=80,key=identity+'contract')
    config={'schema_version':1,'name':name,'dut_top':top,'rtl_files':rtl,'include_files':headers,'editable_files':editable,
        'include_dirs':dirs,'tests':tests,'contract':contract}
    with st.expander('Advanced project manifest'):
        st.caption('Use this for compile order, preprocessor defines, data files, parameters and multi-file testbenches.')
        override=st.text_area('Optional manifest JSON override',value='',height=200,key=identity+'override')
        st.json(config)
        if override:
            try:return json.loads(override)
            except ValueError:st.error('The manifest override is not valid JSON.');return None
    return config


def evidence(folder):
    data=io.BytesIO();root=Path(folder);manifest={}
    with zipfile.ZipFile(data,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(root.rglob('*')):
            if not p.is_file():continue
            name=str(p.relative_to(root))
            if name.endswith('.vvp'):continue
            content=p.read_bytes();archive.writestr(name,content);manifest[name]=sha256(content)
        archive.writestr('evidence-manifest.json',json.dumps(manifest,indent=2))
    return data.getvalue()


def render_result(project,result):
    if result.get('mode')=='independent_fifo_properties':
        from ..property_repair.ui import receipt
        from ..property_repair.contract import load_contract
        receipt(project,load_contract(project),result,Path(result['directory']))
        return
    st.subheader('Project verification')
    final=result.get('final_check') or result.get('baseline',{})
    rows=final.get('tests',[]);passed=sum(t['passed'] for t in rows)
    a,b,c=st.columns(3);a.metric('Provided testbenches' if result.get('final_check') else 'Public discovery tests',f'{passed}/{len(rows)}');b.metric('NVIDIA requests',result['api_requests']);c.metric('Editable files',len(project.config['editable_files']))
    if result['accepted']:st.success('The exact project source passed every provided testbench.')
    else:st.warning('This source was not accepted: '+result['status'])
    first_failed=next((t for t in rows if not t['passed']),None)
    if first_failed:
        st.markdown('**First failing test: '+escape(first_failed['id'])+' · '+first_failed['phase']+'**')
        if first_failed['status']=='ASSERTION_FAILED':st.write('A supplied test assertion failed. Inspect its message below; this source has no checked export.')
        elif first_failed['status']=='INCONCLUSIVE':st.write('The bench did not provide the required completion evidence. Review its success marker and normal exit before treating the result as verified.')
        else:st.write('This check did not complete successfully. Review the diagnostic below and the selected files, compile order, parameters and supported simulator features.')
        st.code((first_failed.get('log_tail') or first_failed.get('error') or first_failed['status'])[-3000:],language='text')
    if result.get('error'):st.error(result['error'])
    ci=result.get('ci_regressions')
    if ci:
        if ci['accepted']:
            st.success('The exact exported CI runner also passed. No model request.')
            st.code('python3 -I rtlrefine_ci/run.py',language='bash')
            st.caption('The checked ZIP includes the standalone checker and .github/workflows/rtlrefine.yml. Commit it at your repository root to recheck pushes and pull requests. JSON and JUnit reports are included in CI artifacts.')
        else:st.error('Standalone CI export rejected: '+ci['status'])
    st.table([{'Test':t['id'],'Phase':t['phase'],'Status':t['status'],'Reported checks':t['checks'] if t['checks'] is not None else 'completion marker',
               'Seconds':round(t['wall_seconds'],3)} for t in rows])
    if not project.audit_tests:st.caption('No additional audit testbench was supplied. The verdict covers only the supplied public checks.')
    if result.get('diagnosis'):
        with st.expander('NVIDIA hypothesis · unverified'):st.write(result['diagnosis'])
    for path,text in result.get('changes',{}).items():
        st.caption(path)
        st.code(''.join(difflib.unified_diff(project.files[path].decode().splitlines(True),text.splitlines(True),fromfile=path,tofile=path)),language='diff')
    with st.expander('Native logs and elaborated interfaces'):
        for test in rows:
            st.markdown('**'+test['id']+' · '+test['status']+'**')
            st.code(test.get('log_tail') or test.get('error') or 'Completed without diagnostic output',language='text')
            if test.get('interface'):st.json(test['interface'])
    root=Path(result['directory']);archive=root/'checked-project.zip'
    if result['accepted'] and archive.exists():
        blob=archive.read_bytes()
        if sha256(blob)!=result['checked_archive_sha256']:st.error('Checked archive changed. Run a new check.')
        else:
            st.download_button('Download checked project ZIP',blob,file_name='checked-project.zip',type='primary',on_click='ignore')
            if ci and ci['accepted']:
                with zipfile.ZipFile(io.BytesIO(blob)) as zipped:
                    workflow=zipped.read('.github/workflows/rtlrefine.yml')
                with st.expander('Included GitHub Actions workflow'):
                    st.code(workflow.decode(),language='yaml')
                    st.download_button('Download CI workflow',workflow,file_name='rtlrefine.yml',on_click='ignore')
    st.download_button('Download project evidence',evidence(root),file_name='project-verification-evidence.zip',on_click='ignore')
    st.caption('Only the submitted tests and configuration were verified. Simulation does not prove unbounded behavior, synthesis timing or physical CDC safety. The earlier 15× screening result does not apply to this mode.')


def render_project():
    st.set_page_config(page_title='RTLRefine · Your project',layout='wide',initial_sidebar_state='collapsed');apply_theme()
    with st.container(key='studio_shell'):
        topbar();st.title('Bring your RTL. Bring your checks.')
        st.write('Upload your design and self-checking testbenches. Check the original, ask NVIDIA for a design-only patch, then rebuild and verify the exact project.')
        st.markdown('<a href="/" target="_self">← Example workspace</a>',unsafe_allow_html=True)
        with st.expander('Try a portable example ZIP'):
            st.caption('These demonstrate the importer; the runner does not restrict projects to these module names or interfaces.')
            st.download_button('Download 129-bit multi-file example',example_zip('wide_math'),file_name='wide-math.zip',on_click='ignore')
            st.download_button('Download two-clock example',example_zip('dual_clock'),file_name='dual-clock.zip',on_click='ignore')
            checked=ROOT/'demo/general_project_ci/axis-register/checked-project.zip'
            if checked.exists():
                st.download_button('Download externally checked project with CI',checked.read_bytes(),file_name='external-rtl-with-ci.zip',on_click='ignore')
                st.caption('The prior actual NVIDIA-selected external repair, now packaged with reusable checks. No new repair request was made.')
            uart=ROOT/'demo/uart_peer/projects/uart-nvidia-checked-ci.zip'
            if uart.exists():
                st.download_button('Download checked external UART pair with CI',uart.read_bytes(),file_name='uart-peer-checked-ci.zip',on_click='ignore')
        upload=st.file_uploader('RTL project ZIP',type=['zip'],help='10 MiB compressed, 32 MiB expanded, up to 256 entries. Never include credentials or .env files.')
        if upload is None:
            st.info('Include rtlrefine.json for an existing configuration, or choose the file roles after upload. Testbenches must use a literal success marker or `RTLREFINE_DONE(check_count). Passing general projects export standalone checks and a GitHub Actions workflow.')
            return
        blob=upload.getvalue();identity=sha256(blob)[:16]
        try:
            files=read_archive(blob)
            if 'rtlrefine.json' in files:
                project=load_project(files)
                with st.expander('Imported project configuration'):st.json(project.config)
            else:
                config=wizard(files,identity)
                if config is None:return
                project=load_project(files,config)
            if any(p=='rtlrefine_regressions' or p.startswith('rtlrefine_regressions/') for p in project.files):
                from ..property_repair.contract import load_contract,bind_contract
                project=bind_contract(project,load_contract(project))
        except (ValueError,UnicodeError,KeyError,TypeError) as exc:st.error(str(exc));return
        st.html('<div class="studio-section-head"><span class="studio-eyebrow">'+escape(project.config['name'])+'</span>'+badge('User testbench project','saved')+'</div>')
        st.caption('DUT: '+project.config['dut_top']+' · '+str(len(project.config['rtl_files']))+' RTL files · '+str(len(project.public_tests))+' public tests · '+str(len(project.audit_tests))+' additional tests')
        with st.expander('Inspect submitted files'):
            path=st.selectbox('File',list(project.files),key=identity+'file')
            try:st.code(project.files[path].decode(),language='verilog' if Path(path).suffix in ('.v','.sv','.vh','.svh') else 'text')
            except UnicodeDecodeError:st.caption('Binary data asset · '+str(len(project.files[path]))+' bytes')
        missing=[name for name in ('iverilog','vvp','bwrap','prlimit') if not find_tool(name)]
        if 'rtlrefine_regressions/manifest.json' in project.files:
            st.info('This export retains its FIFO contract and regression suite. A full check runs both as well as the supplied benches.')
            if not find_tool('yosys'):missing.append('yosys')
        owner=os.getenv('RTLREFINE_ENABLE_LIVE_MODEL')=='1';a,b=st.columns(2)
        check=a.button('Check this project',type='primary',disabled=bool(missing),width='stretch')
        fix=b.button('Repair this project with NVIDIA',disabled=bool(missing) or not owner,width='stretch')
        st.caption('Checking makes no model request. Repair sends editable RTL, declared design dependencies and public testbench text to Nebius, at most twice. Additional testbench source/results are withheld until selection is fixed.')
        if missing:st.info('Native tools required: '+', '.join(missing))
        if check or fix:
            st.session_state.pop('generic_project_result',None)
            try:
                with st.status('Working on the submitted project…',expanded=True) as status:
                    with execution_slot():result=run_project(project,repair=fix,on_event=lambda e:st.write(e['message']))
                    status.update(label='Project checked' if result['accepted'] else 'Finished; inspect verification results',state='complete' if result['accepted'] else 'error',expanded=False)
                st.session_state['generic_project_result']=result
            except (ValueError,RuntimeError,OSError,KeyError) as exc:st.error(str(exc))
        current=st.session_state.get('generic_project_result')
        if current and current['project_id']==project.identity:render_result(project,current)


if __name__=='__main__':render_project()
