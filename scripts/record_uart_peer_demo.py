"""Continuous normal-speed UART/general-CI/FIFO demo; recorded model runs labeled."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.record_submission_2026 import stamp,ass_stamp


def main():
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8557');p.add_argument('--output',default='submission/uart-peer-v1');a=p.parse_args()
    out=ROOT/a.output;out.mkdir(exist_ok=True);video=out/'video';video.mkdir(exist_ok=False)
    screens=out/'screenshots';screens.mkdir(exist_ok=True)
    ledger=(ROOT/'.state/spend.json').read_bytes();captions=[];errors=[]
    with sync_playwright() as w:
        browser=w.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu'])
        context=browser.new_context(viewport={'width':1600,'height':800},record_video_dir=str(video/'raw'),record_video_size={'width':1600,'height':800},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));captured=time.monotonic()
        page.goto(a.url+'/external-validation',wait_until='domcontentloaded')
        title=page.get_by_role('heading',name='UART · loopback and independent serial peers',exact=True)
        expect(title).to_be_visible(timeout=30000);title.scroll_into_view_if_needed()
        start=time.monotonic();trim=start-captured
        def hold(text,seconds):
            t=time.monotonic()-start;print(f'{t:.1f}s {text}',flush=True)
            page.wait_for_timeout(seconds*1000);captions.append((t,time.monotonic()-start,text))
        hold('RTLRefine: check an AI repair and keep executable regressions.\nModel results are actual recorded runs; the native checks below execute fresh.',7)
        page.get_by_role('button',name='Run original loopback-only smoke without inference',exact=True).click()
        expect(page.get_by_text('Loopback-only smoke passed. This does not check the independent LSB-first peer contract. Zero model requests.',exact=True)).to_be_visible(timeout=30000)
        page.get_by_text('Loopback-only smoke passed. This does not check the independent LSB-first peer contract. Zero model requests.',exact=True).scroll_into_view_if_needed()
        hold('This historical UART pair passes its closed-loop smoke test.\nA matching transmitter and receiver can conceal the same wrong bit order.',7)
        page.get_by_role('button',name='Reproduce original UART peer mismatch without inference',exact=True).click()
        expect(page.get_by_text('Original UART peer mismatch reproduced. No checked export. Zero model requests.',exact=True)).to_be_visible(timeout=30000)
        page.get_by_text('Original UART peer mismatch reproduced. No checked export. Zero model requests.',exact=True).scroll_into_view_if_needed()
        hold('The supplied independent serial-peer test rejects it. No checked export.\nExpected data comes from offered bytes, not corrected reference RTL.',7)
        page.get_by_text('Captured data-bit centers',exact=True).scroll_into_view_if_needed()
        hold('Actual bit-center samples: 0x01 becomes 0x80 on the original wire.\nThe original receiver reverses bytes too. The selected repair corrects both.',11)
        page.screenshot(path=str(screens/'01-actual-peer-bit-order.png'))
        page.get_by_text('Actual saved Nebius request and response metadata',exact=True).click()
        meta=page.get_by_test_id('stExpander').filter(has_text='Actual saved Nebius request and response metadata')
        meta.get_by_test_id('stJson').scroll_into_view_if_needed()
        hold('Actual recorded Nemotron response on Nebius Token Factory.\nSix development requests are retained; the final two-request run passed.',10)
        page.screenshot(path=str(screens/'02-actual-nebius-record.png'))
        page.get_by_text('Actual source changes and every development run',exact=True).click()
        page.get_by_test_id('stCode').filter(has_text='--- original/rtl/uart_rx.v').scroll_into_view_if_needed()
        hold('The agent changes the real vendor RX file. Headers and ports stay fixed.\nAll earlier wrong, uncompilable and truncated responses remain in the evidence.',5)
        page.get_by_test_id('stCode').filter(has_text='--- original/rtl/uart_tx.v').scroll_into_view_if_needed()
        hold('Its selected TX edit corrects serialization too. Both leaves are rebuilt independently\ninside the read-only adapter; no corrected implementation is the test oracle.',5)
        page.get_by_role('button',name='Recheck UART repair and CI without inference',exact=True).click()
        expect(page.get_by_text('Fresh UART peer and exported CI checks passed. Zero model requests.',exact=True)).to_be_visible(timeout=60000)
        page.get_by_text('Fresh UART peer and exported CI checks passed. Zero model requests.',exact=True).scroll_into_view_if_needed()
        hold('Fresh verification: eight fixed profiles and the exact standalone CI runner pass.\n5-8 data bits, serial frames, resets, backpressure and overrun: 186,772 evaluations.',9)
        with page.expect_download() as pending:page.get_by_role('button',name='Download freshly checked UART with CI',exact=True).click()
        pending.value.save_as(str(video/'checked-uart-ci.zip'))
        page.get_by_role('button',name='Run exported UART regression cycle without inference',exact=True).click()
        expect(page.get_by_text('Exported UART CI reproduced 0 → 1 → 0. Zero model requests.',exact=True)).to_be_visible(timeout=60000)
        page.get_by_test_id('stTable').filter(has_text='bug_reintroduced').evaluate("e=>e.scrollIntoView({block:'center'})")
        hold('The downloaded checker runs on checked source, both original files, then restored source.\nExit codes 0, 1, 0: a returning defect fails the same unchanged tests.',10)
        page.screenshot(path=str(screens/'03-real-uart-ci-cycle.png'))
        page.goto(a.url+'/project',wait_until='domcontentloaded')
        page.locator('input[type=file]').set_input_files(str(video/'checked-uart-ci.zip'))
        expect(page.get_by_role('button',name='Repair this project with NVIDIA',exact=True)).to_be_disabled()
        page.get_by_role('button',name='Check this project',exact=True).click()
        expect(page.get_by_text('The exact exported CI runner also passed. No model request.',exact=True)).to_be_visible(timeout=60000)
        page.get_by_text('The exact exported CI runner also passed. No model request.',exact=True).scroll_into_view_if_needed()
        hold('Reopen the same three-file UART project through the general ZIP workspace.\nIts protected tests and reusable CI remain attached; no model key is needed.',8)
        page.get_by_text('Included GitHub Actions workflow',exact=True).click()
        page.get_by_role('button',name='Download CI workflow',exact=True).scroll_into_view_if_needed()
        hold('Commit the included workflow to recheck pushes and pull requests.\nJSON and JUnit reports distinguish pass, design regression and setup failure.',8)
        page.goto(a.url+'/properties',wait_until='domcontentloaded')
        page.get_by_role('button',name='Find hidden failures without NVIDIA',exact=True).click()
        expect(page.get_by_text('No checked export: INDEPENDENT_FAILURE_FOUND',exact=True)).to_be_visible(timeout=60000)
        page.get_by_role('heading',name='Independent verification',exact=True).scroll_into_view_if_needed()
        hold('For the separate supported FIFO contract, symbolic checks find a missed case.\nThis authored fixture passes smoke tests; its failure is replayed against a Python queue.',10)
        page.screenshot(path=str(screens/'04-independent-fifo-counterexample.png'))
        page.get_by_role('button',name='Show saved repair and evidence',exact=True).click()
        expect(page.get_by_text('Saved actual NVIDIA run',exact=True)).to_be_visible()
        page.get_by_test_id('stCode').filter(has_text='--- rtl/packet_queue.sv').scroll_into_view_if_needed()
        hold('This earlier actual NVIDIA FIFO repair is explicitly recorded.\nFinal bounded checks and portable regressions accompany its selected source.',8)
        hold('Known external UART development and authored bounded FIFO examples; no unseen accuracy\nor physical timing/CDC claim. Source and test build: github.com/ehdtjq08/RTLRefine',8)
        seconds=time.monotonic()-start;assert seconds<177,seconds
        raw=Path(page.video.path());context.close();browser.close()
    assert not errors and ledger==(ROOT/'.state/spend.json').read_bytes()
    header=(ROOT/'submission/functional-v1/video/captions.ass').read_text().split('[Events]')[0]
    events='[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
    (video/'captions.ass').write_text(header+events+''.join(f'Dialogue: 0,{ass_stamp(t)},{ass_stamp(end)},Default,,0,0,0,,'+text.replace('\n',r'\N')+'\n' for t,end,text in captions))
    (video/'captions.srt').write_text(''.join(f'{i}\n{stamp(t)} --> {stamp(end)}\n{text}\n\n' for i,(t,end,text) in enumerate(captions,1)).rstrip()+'\n')
    final=video/'RTLRefine-UART-peer-demo.mp4'
    subprocess.run(['ffmpeg','-y','-ss',str(trim),'-i',str(raw),'-t',str(seconds),'-vf','scale=1920:960,pad=1920:1080:0:0:color=0x0b1117,ass=captions.ass','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','20','-pix_fmt','yuv420p','-r','30','-movflags','+faststart',str(final)],cwd=video,check=True,capture_output=True)
    duration=float(json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(final)],check=True,capture_output=True,text=True).stdout)['format']['duration']);assert duration<180
    report={'status':'PASS','video_seconds':duration,'video_sha256':hashlib.sha256(final.read_bytes()).hexdigest(),'continuous_normal_speed_recording':True,
            'recorded_model_results_labeled':True,'uart_development_requests_disclosed':6,'uart_final_run_requests':2,'new_model_calls_during_recording':0,
            'fresh_peer_failure_and_limited_loopback_pass':True,'fresh_uart_repair_and_ci':True,'fresh_exported_ci_cycle':[0,1,0],
            'same_zip_general_import_rechecked':True,'fresh_fifo_counterexample':True,'authored_bounded_scope_disclosed':True,'browser_errors':errors,'youtube_uploaded':False}
    (video/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
