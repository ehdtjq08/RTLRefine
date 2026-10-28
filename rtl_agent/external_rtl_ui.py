"""Replay independently authored RTL validation; no new inference is made here."""
import difflib
import json
from pathlib import Path

import streamlit as st

from .common import ROOT,sha256
from .studio_theme import apply_theme,topbar
from .project_repair.project import read_archive,load_project
from .project_repair.workflow import run_project
from .project_repair.ui import evidence
from workspace_service import execution_slot

DATA=ROOT/'demo/external_rtl_validation'


def read(path):return json.loads(path.read_text())


def matrix(folder):
    result=read(folder/'result.json');config=read(folder/'project.json')
    tests=result.get('final_check',result['baseline'])['tests'];settings={t['id']:t for t in config['tests']}
    st.table([{'Profile':t['id'],'Data bits':int(settings[t['id']]['parameters'].get('DATA_WIDTH','8')),
               'Mode':{'0':'bypass','1':'simple/combinational output','2':'skid/registered output'}[str(settings[t['id']]['parameters'].get('REG_TYPE','2'))],
               'Assertions':t['checks'],'Status':t['status']} for t in tests])


def recheck(label,project_path,*,expected=True):
    blob=project_path.read_bytes();identity=sha256(blob);key='external_recheck_'+identity
    if st.button(label,key=key+'button',width='stretch'):
        try:
            with st.status('Running the ordinary project checker…',expanded=True) as status:
                with execution_slot():result=run_project(load_project(read_archive(blob)),on_event=lambda e:st.write(e['message']))
                status.update(label='Fresh check complete',state='complete')
            st.session_state[key]=result
        except (ValueError,RuntimeError,OSError) as exc:st.error(str(exc))
    result=st.session_state.get(key)
    if result:
        if result['accepted'] and expected:st.success('Fresh external project recheck passed. Zero model requests.')
        elif not expected and result['status']=='PUBLIC_TESTS_FAILED' and any(
            t['id']=='capacity_public' and t['status']=='ASSERTION_FAILED'
            and 'CAPACITY_READY_REGRESSION' in t.get('log_tail','')
            for t in result.get('baseline',{}).get('tests',[])
        ):st.warning('Known upstream capacity/throughput regression reproduced. No checked export. Zero model requests.')
        else:st.error('The recheck did not match the recorded outcome: '+result['status'])
        with st.expander('Fresh check record'):st.json(result)


def render_external():
    st.set_page_config(page_title='RTLRefine · External RTL',layout='wide',initial_sidebar_state='collapsed');apply_theme()
    with st.container(key='studio_shell'):
        topbar();st.title('Validated on independently developed RTL.')
        st.write('A real upstream regression repaired through the ordinary ZIP workflow, plus an unmodified healthy module from a second author. Recheck the exact projects without a model request.')
        st.page_link('project_app.py',label='Open the general project workspace',icon=':material/folder_open:')
        summary=read(DATA/'summary.json');first,second=st.tabs(['Known upstream regression repair','Second-author healthy control'])
        with first:
            r=summary['axis_register'];folder=DATA/'axis_register/repaired/run';record=read(folder/'result.json')
            st.subheader('verilog-axis · AXI4-Stream register')
            st.markdown('[Regressed upstream commit](https://github.com/alexforencich/verilog-axis/commit/6d4458e5cc15df401b82a8fd615b3216e6a61d0e) · [Maintainer revert](https://github.com/alexforencich/verilog-axis/commit/b9e0af36341a81ae80d6a8467b029d79c69b71cb) · MIT license retained')
            st.caption('Known early-ready throughput/capacity regression; not a new discovery or an unconditional AXI protocol violation. Healthy parent, revert and current source have identical file hashes and count as one implementation.')
            a,b,c=st.columns(3);a.metric('Provided testbenches','8/8');b.metric('Assertion evaluations',f"{r['assertions']:,}");c.metric('Actual recorded NVIDIA requests',r['actual_model_requests'])
            st.success('The exact NVIDIA-selected source passed all eight benches and a fresh export reimport.')
            st.write('After one word is accepted, an input-idle gap while output remains stalled should leave the second skid slot available. The regressed revision stops accepting that second word. The test checks this behavior from external handshakes.')
            original=read_archive((folder/'original-project.zip').read_bytes())['rtl/axis_register.v'].decode()
            selected=record['changes']['rtl/axis_register.v']
            assert sha256(selected.encode())==record['selected_design_hashes']['rtl/axis_register.v']
            st.code(''.join(difflib.unified_diff(original.splitlines(True),selected.splitlines(True),fromfile='upstream-regressed.v',tofile='checked-nvidia-repair.v')),language='diff')
            st.caption('Actual recorded run: '+f"{r['wall_seconds']:.2f}s"+' including tools; estimated inference cost $'+f"{r['estimated_inference_cost_usd']:.6f}"+'. One exposed development case, not a general model benchmark. No current/parent/revert source or private audit bench was sent to the model.')
            matrix(folder)
            good=DATA/'projects/axis-register-nvidia-repaired.zip';bad=DATA/'projects/axis-register-regressed.zip'
            st.download_button('Download externally checked NVIDIA repair',good.read_bytes(),file_name=good.name,type='primary',on_click='ignore')
            st.download_button('Download unmodified upstream regression',bad.read_bytes(),file_name=bad.name,on_click='ignore')
            st.download_button('Download external repair evidence',evidence(folder),file_name='external-axis-evidence.zip',on_click='ignore')
            recheck('Recheck external NVIDIA repair without inference',good)
            recheck('Reproduce upstream regression without inference',bad,expected=False)
        with second:
            r=summary['zipcpu_skid'];folder=DATA/'zipcpu_skid/healthy/run'
            st.subheader('ZipCPU · skid buffer')
            st.markdown('[Pinned unmodified upstream source](https://github.com/ZipCPU/wb2axip/blob/2e8d3bc2d26ddc33d1881022a2a2b9d3f0c16b9b/rtl/skidbuffer.v) · Apache 2.0 source header and license retained')
            st.caption('Healthy compatibility control. A disclosed stateless adapter packs AXI sidebands into the leaf data bus; the upstream skid buffer is unmodified. No bug discovery or model repair is claimed here.')
            a,b,c=st.columns(3);a.metric('Provided testbenches','8/8');b.metric('Assertion evaluations',f"{r['assertions']:,}");c.metric('Model requests',0)
            matrix(folder)
            project=DATA/'projects/zipcpu-skid-healthy.zip'
            st.download_button('Download second-author healthy project',project.read_bytes(),file_name=project.name,on_click='ignore')
            recheck('Recheck ZipCPU healthy control without inference',project)
        st.caption('Independent transaction scoreboards mask invalid TKEEP bytes, preserve legal source stability, and check order, metadata, stalls, reset flushing, conservation and drain. Two explicit observed-data corruption controls fail as expected. These finite parameter profiles do not prove unbounded protocol correctness, timing, power, CDC safety or unseen repair accuracy.')
