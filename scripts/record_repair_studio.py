"""Record the actual product, one bounded live agent run and a rejected partial fix."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

from playwright.sync_api import expect,sync_playwright

ROOT=Path(__file__).resolve().parent.parent


def stamp(seconds):
    value=round(seconds*1000);h,value=divmod(value,3600000);m,value=divmod(value,60000);s,value=divmod(value,1000)
    return f'{h:02}:{m:02}:{s:02},{value:03}'


def main():
    output=ROOT/'submission/studio-v1/video';output.mkdir(parents=True,exist_ok=False);captions=[];errors=[]
    existing=set((ROOT/'results').glob('*_guided_batch_repair'))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu','--renderer-process-limit=1'])
        context=browser.new_context(viewport={'width':1440,'height':1000},record_video_dir=str(output/'raw'),record_video_size={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        captured=time.monotonic();page.goto('http://127.0.0.1:8504',wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='An AI fix needs evidence.',exact=True)).to_be_visible(timeout=30000)
        start=time.monotonic();trim=start-captured
        def hold(text,seconds):
            begin=time.monotonic()-start;print(f'{begin:.1f}s: {text}',flush=True)
            page.wait_for_timeout(seconds*1000);captions.append((begin,time.monotonic()-start,text))
        hold('RTLRefine: from a failing RTL trace to an exact checked patch.\nNVIDIA Nemotron on Nebius guides a bounded repair search.',7)
        page.locator('.st-key-studio_trace').scroll_into_view_if_needed()
        hold('This historical packet FIFO can publish the tail of a dropped frame.\nCaptured output, expected behavior and the source change stay together.',8)
        page.get_by_role('button',name='Diagnose and repair with NVIDIA',exact=True).scroll_into_view_if_needed()
        begin=time.monotonic()-start
        page.get_by_role('button',name='Diagnose and repair with NVIDIA',exact=True).click()
        expect(page.get_by_text(re.compile(r'^Fresh run ·'))).to_be_visible(timeout=90000)
        captions.append((begin,time.monotonic()-start,'A real live NVIDIA request through Nebius Token Factory.\nOnly public failure information reaches the agent before patch selection.'))
        expect(page.get_by_text('The exact patch passed all three fixed profiles.',exact=True)).to_be_visible()
        page.get_by_text('NVIDIA hypotheses · unverified',exact=True).click();page.get_by_text('Nemotron diagnosis',exact=True).scroll_into_view_if_needed()
        hold('The model suggests existing source-generated patch IDs.\nThe exact selected file is then rebuilt and independently checked.',10)
        page.get_by_role('button',name='Recheck this exact patch',exact=True).click()
        expect(page.get_by_text('Fresh recheck passed · exact source hash verified.',exact=True)).to_be_visible(timeout=60000)
        hold('Fresh recheck: the selected patch passes the public profile and two audits.\nThese are fixed two-state trace checks, not unbounded hardware correctness.',9)
        with page.expect_download() as item:page.get_by_role('button',name='Download checked RTL',exact=True).click()
        item.value.save_as(str(output/'checked.v'))
        with page.expect_download() as item:page.get_by_role('button',name='Download verification evidence',exact=True).click()
        item.value.save_as(str(output/'live-run-evidence.zip'))
        hold('Export the exact checked RTL, traces, model response, tool logs and hashes.\nThe checked source cannot silently change after verification.',8)
        page.get_by_text('Screening benchmark · measurement & scope',exact=True).click()
        expect(page.get_by_test_id('stMetric').filter(has_text='Measured complete-pool screening throughput')).to_be_visible()
        page.get_by_test_id('stMetric').filter(has_text='Measured complete-pool screening throughput').scroll_into_view_if_needed()
        hold('Same 118 candidates: 208.1 seconds with separate builds, 13.9 seconds with sharing.\nAll results match. One paired run per case; this is screening throughput.',12)
        page.get_by_test_id('stSelectbox').filter(has_text='Choose a real RTL failure').get_by_role('combobox').click()
        page.get_by_role('option',name='Reset leaves stale packet state',exact=True).click()
        page.get_by_role('tab',name='Edit source',exact=True).click()
        pool=json.loads((ROOT/'results/repair_search_pools_v1_20261023/case_09/pool.json').read_text())
        partial=next(c for c in pool if c['id']=='candidate_001')['rtl']
        field=page.get_by_test_id('stTextArea').locator('textarea');field.fill(partial);field.press('Tab')
        hold('Now try a deliberately incomplete reset patch.\nA stale success disappears immediately when the source changes.',8)
        begin=time.monotonic()-start;page.get_by_role('button',name='Run bounded local search',exact=True).click()
        expect(page.get_by_text('The selected patch failed independent checks and was not accepted.',exact=True)).to_be_visible(timeout=60000)
        captions.append((begin,time.monotonic()-start,'The partial patch passes the public profile.\nAdditional audit traces still have to pass before export.'))
        page.get_by_text('The selected patch failed independent checks and was not accepted.',exact=True).scroll_into_view_if_needed()
        hold('Rejected: only 1 of 3 profiles passes. No checked-RTL download is offered.\nThe failed observations remain available for review.',10)
        hold('Browser workflow, real NVIDIA calls and isolated native tools.\nThree supported historical examples; full development failures remain recorded.',8)
        duration=time.monotonic()-start;raw=Path(page.video.path());context.close();browser.close()
    assert not errors and duration<177
    new=set((ROOT/'results').glob('*_guided_batch_repair'))-existing
    live=[]
    for folder in new:
        p=folder/'result.json'
        if p.exists():
            r=json.loads(p.read_text())
            if r['api_requests']:live.append((folder,r))
    assert len(live)==1 and live[0][1]['accepted'] and 1<=live[0][1]['api_requests']<=2
    assert hashlib.sha256((output/'checked.v').read_bytes()).hexdigest()==live[0][1]['selected_sha256']
    (output/'captions.srt').write_text(''.join(f'{i}\n{stamp(a)} --> {stamp(b)}\n{text}\n\n' for i,(a,b,text) in enumerate(captions,1)))
    video=output/'RTLRefine-repair-studio-demo.mp4'
    filters="subtitles=captions.srt:force_style='FontName=DejaVu Sans,FontSize=17,Outline=1,Shadow=0,MarginV=16'"
    subprocess.run(['ffmpeg','-y','-ss',str(trim),'-i',str(raw),'-t',str(duration),'-vf',filters,'-an','-c:v','libx264','-threads','2','-preset','fast','-crf','21','-pix_fmt','yuv420p','-r','30','-movflags','+faststart',str(video)],cwd=output,check=True,capture_output=True)
    probe=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(video)],text=True,capture_output=True,check=True)
    seconds=float(json.loads(probe.stdout)['format']['duration']);assert seconds<180
    report={'status':'PASS','video_seconds':seconds,'video_sha256':hashlib.sha256(video.read_bytes()).hexdigest(),
        'actual_ui_recorded':True,'new_model_calls':live[0][1]['api_requests'],'live_run_directory':str(live[0][0]),
        'live_run_accepted':True,'fresh_recheck_in_video':True,'partial_patch_rejection_in_video':True,'browser_errors':errors,
        'screening_speed_scope_disclosed':True,'unbounded_correctness_claimed':False,'publicly_uploaded':False}
    (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
