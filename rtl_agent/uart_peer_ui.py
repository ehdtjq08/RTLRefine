"""Show captured UART peer samples and fresh checks; this page makes no inference."""
import difflib
from html import escape
import json
from pathlib import Path
import re

import streamlit as st

from .common import ROOT, sha256, new_run_dir, write_json
from .project_repair.ci_bundle import check_bundle
from .project_repair.project import load_project, read_archive
from .project_repair.workflow import run_project
from workspace_service import execution_slot

DATA = ROOT / 'demo/uart_peer'


def read(path):
    return json.loads(path.read_text())


def public_log(record):
    return next(t['log_tail'] for t in record.get('final_check', record['baseline'])['tests'] if t['id'] == 'public_peer')


def tx_samples(log):
    return {int(word, 16): int(observed, 16) for word, observed in re.findall(r'UART_TX_FRAME offered=([0-9a-fA-F]+) observed_lsb=([0-9a-fA-F]+)', log)}


def sample_table(word, original, selected):
    header = '<tr><th>Captured data-bit centers</th>' + ''.join(f'<th>d{i}</th>' for i in range(8)) + '<th>Decoded byte</th></tr>'
    rows = []
    for name, value in [('Declared LSB-first peer', word), ('Original transmitter', original), ('NVIDIA-selected transmitter', selected)]:
        cells = []
        for i in range(8):
            bit, expected = (value >> i) & 1, (word >> i) & 1
            mark = 'color:#ff928c;background:#382326;font-weight:700' if bit != expected else 'color:#c9efbb;background:#172b24'
            cells.append(f'<td style="{mark};text-align:center;padding:12px">{bit}</td>')
        rows.append('<tr><th style="text-align:left;padding:10px">' + escape(name) + '</th>' + ''.join(cells) + f'<td style="padding:12px">0x{value:02X}</td></tr>')
    st.html('<table style="width:100%;border-collapse:separate;border-spacing:3px">' + header + ''.join(rows) + '</table>')


def recheck(label, path, kind):
    blob = path.read_bytes()
    key = 'uart_peer_' + sha256(blob)
    if st.button(label, key=key + '_button', width='stretch'):
        st.session_state.pop(key, None)
        try:
            with st.status('Running the ordinary project checker…', expanded=True) as status:
                with execution_slot():
                    result = run_project(load_project(read_archive(blob)), on_event=lambda e: st.write(e['message']))
                status.update(label='Fresh UART check complete', state='complete')
            st.session_state[key] = result
        except (ValueError, RuntimeError, OSError) as exc:
            st.error(str(exc))
    result = st.session_state.get(key)
    if not result:
        return
    if kind == 'repair' and result['accepted'] and result.get('ci_regressions', {}).get('accepted'):
        st.success('Fresh UART peer and exported CI checks passed. Zero model requests.')
        archive = Path(result['directory']) / 'checked-project.zip'
        checked = archive.read_bytes()
        if sha256(checked) == result['checked_archive_sha256']:
            st.download_button('Download freshly checked UART with CI', checked, file_name='uart-checked-ci.zip', key=key + '_download', on_click='ignore')
    elif kind == 'smoke' and result['accepted']:
        st.warning('Loopback-only smoke passed. This does not check the independent LSB-first peer contract. Zero model requests.')
    elif kind == 'original' and result['status'] == 'PUBLIC_TESTS_FAILED' and any(
        t['status'] == 'ASSERTION_FAILED' and 'UART_PEER_CONTRACT_FAILED' in t.get('log_tail', '')
        for t in result.get('baseline', {}).get('tests', [])
    ):
        st.warning('Original UART peer mismatch reproduced. No checked export. Zero model requests.')
    else:
        st.error('The check did not reproduce the expected outcome: ' + result['status'])
    with st.expander('Fresh UART check record'):
        st.json(result)


def regression_cycle():
    blob=(DATA/'projects/uart-nvidia-checked-ci.zip').read_bytes()
    key='uart_ci_cycle_'+sha256(blob)
    if st.button('Run exported UART regression cycle without inference',width='stretch'):
        st.session_state.pop(key,None)
        try:
            folder=new_run_dir('uart_exported_ci_cycle');files=read_archive(blob)
            upstream=ROOT/'external_cases/uart_bitorder_external'
            provenance=read(upstream/'provenance.json');bad=dict(files)
            for name in ('uart_tx.v','uart_rx.v'):
                original=(upstream/'original/rtl'/name).read_bytes()
                if sha256(original)!=provenance['revision']['original']['files'][name]['sha256']:
                    raise ValueError('Pinned original UART source changed')
                bad['rtl/'+name]=original
            rows=[]
            with st.status('Running the exact exported CI command on three source states…',expanded=True) as status:
                with execution_slot():
                    for phase,content in [('checked',files),('bug_reintroduced',bad),('restored',files)]:
                        result=check_bundle(load_project(content),folder/phase)
                        rows.append({'Source':phase,'Exit':result.get('standalone_exit_code'),'Status':result['status']})
                        st.write(rows[-1])
                passed=[r['Exit'] for r in rows]==[0,1,0] and [r['Status'] for r in rows]==['REGRESSIONS_PASS','REGRESSION_FAILED','REGRESSIONS_PASS']
                status.update(label='Exported CI cycle complete',state='complete' if passed else 'error')
            report={'status':'PASS' if passed else 'NOT_REPRODUCED','rows':rows,'new_model_calls':0,'input_archive_sha256':sha256(blob)}
            write_json(folder/'cycle.json',report);st.session_state[key]=report
        except (ValueError,RuntimeError,OSError) as exc:st.error(str(exc))
    result=st.session_state.get(key)
    if result:
        if result['status']=='PASS':st.success('Exported UART CI reproduced 0 → 1 → 0. Zero model requests.')
        else:st.error('The exported regression cycle did not reproduce the expected outcomes.')
        st.table(result['rows'])


def render_uart_peer():
    if not (DATA / 'summary.json').exists():
        st.info('UART peer evidence is not included in this older build.')
        return
    summary = read(DATA / 'summary.json')
    original = read(DATA / 'qualification/original_peer/result.json')
    selected = read(DATA / 'development/run3/result.json')
    st.subheader('UART · loopback and independent serial peers')
    st.write('The original transmitter and receiver agree with each other, yet reverse bytes at an LSB-first serial peer. The same general ZIP workflow repairs both files and exports their reusable checks.')
    st.markdown('[Pinned original UART pair](https://github.com/alexforencich/verilog-uart/tree/62eb6f5d45b62be3029308da58c64bafbdb3aac6/rtl) · [Upstream LSB-first change](https://github.com/alexforencich/verilog-uart/commit/db0017a22c57731d69a4a2844bc1e4f3f36abd10) · MIT license retained')
    st.caption('Known historical bit-order change, evaluated against an explicit LSB-first peer contract. Not a new discovery or an introduced regression. A disclosed stateless read-only adapter exposes both vendor modules; it never reverses data.')
    a, b, c = st.columns(3)
    a.metric('Original closed-loop smoke', 'PASS', help='678 assertion evaluations cover only this limited loopback test.')
    b.metric('NVIDIA-selected peer profiles', '8/8')
    c.metric('Peer assertion evaluations', f"{summary['assertion_evaluations']:,}")
    old_samples, new_samples = tx_samples(public_log(original)), tx_samples(public_log(selected))
    word = st.selectbox('Inspect a captured public word', list(old_samples), format_func=lambda v: f'0x{v:02X}', key='uart_peer_word')
    sample_table(word, old_samples[word], new_samples[word])
    st.caption('Each cell is an actual sample at a data-bit center from the recorded public test. Start/stop bits and continuous timing are omitted here; the checker verifies every tested bit cell. Highlighted cells disagree with the declared peer.')
    old_rx = {int(a, 16): int(b, 16) for a, b in re.findall(r'UART_RX_FRAME sent_lsb=([0-9a-fA-F]+) decoded=([0-9a-fA-F]+)', public_log(original))}
    new_rx = {int(a, 16): int(b, 16) for a, b in re.findall(r'UART_RX_FRAME sent_lsb=([0-9a-fA-F]+) decoded=([0-9a-fA-F]+)', public_log(selected))}
    st.table([{'Independent peer sends': f'0x{v:02X}', 'Original RX publishes': f'0x{old_rx[v]:02X}', 'Selected RX publishes': f'0x{new_rx[v]:02X}'} for v in old_rx])
    st.success('Both selected vendor files passed all eight fixed peer profiles and the exact exported standalone CI runner.')
    st.caption(f"Recorded development: {summary['development_model_requests']} actual requests across three runs, application-estimated ${summary['development_estimated_cost_usd']:.6f}. The first four requests failed; the last run used two requests and passed. This is exposed development, not an unseen accuracy estimate or proof that one inference setting is generally better.")
    with st.expander('Actual source changes and every development run'):
        for path, text in selected['changes'].items():
            old = (ROOT / 'external_cases/uart_bitorder_external/original' / path).read_text()
            assert sha256(text.encode()) == selected['selected_design_hashes'][path]
            st.code(''.join(difflib.unified_diff(old.splitlines(True), text.splitlines(True), fromfile='original/' + path, tofile='selected/' + path)), language='diff')
        st.table(summary['development_runs'])
        st.caption('The first two runs used a 6,144-token cap for each request. The final run allowed 12,288 tokens for the reasoning-enabled revision. Tests were unchanged; final audit results were never revision feedback.')
    with st.expander('Actual saved Nebius request and response metadata'):
        response=read(DATA/'development/run3/proposal_2/response.json')
        request=read(DATA/'development/run3/proposal_2/request_started.json')
        st.json({'provider':'Nebius Token Factory','model':response.get('model'),'finish_reason':response['choices'][0]['finish_reason'],
                 'usage':response.get('usage'),'request_controls':request,'run_wall_seconds':selected['wall_seconds'],
                 'run_requests':selected['api_requests'],'all_development_requests':summary['development_model_requests']})
        st.caption('This is an actual recorded response. The replay buttons execute native checks fresh and never request a new model response.')
    with st.expander('Peer profiles and retained failures'):
        config = read(DATA / 'development/run3/project.json')
        settings = {t['id']: t['parameters'] for t in config['tests']}
        st.table([{'Profile': t['id'], 'Data bits': settings[t['id']]['DATA_WIDTH'], 'Clocks per bit': int(settings[t['id']]['PRESCALE']) * 8,
                   'Status': t['status'], 'Assertions': t['checks']} for t in selected['final_check']['tests']])
        st.code(public_log(original), language='text')
    good = DATA / 'projects/uart-nvidia-checked-ci.zip'
    st.download_button('Download checked UART pair with CI', good.read_bytes(), file_name=good.name, type='primary', on_click='ignore')
    st.download_button('Download original UART peer project', (DATA / 'projects/uart-original-peer.zip').read_bytes(), file_name='uart-original-peer.zip', on_click='ignore')
    recheck('Recheck UART repair and CI without inference', good, 'repair')
    recheck('Reproduce original UART peer mismatch without inference', DATA / 'projects/uart-original-peer.zip', 'original')
    recheck('Run original loopback-only smoke without inference', DATA / 'projects/uart-original-loopback-only.zip', 'smoke')
    regression_cycle()
    st.caption('The public and audit benches share the declared protocol monitor; seven additional parameter/seed profiles were withheld. Finite 5–8-bit, no-parity simulations cover serial bits, handshakes, framing, overrun and reset. They do not prove unbounded UART correctness, physical timing or CDC safety.')
