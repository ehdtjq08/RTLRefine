"""Record actual constrained-search UI and a no-model selected-source recheck."""
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
    total=round(seconds*1000);h,total=divmod(total,3600000);m,total=divmod(total,60000);s,total=divmod(total,1000)
    return f'{h:02}:{m:02}:{s:02},{total:03}'


def main():
    out=ROOT/'submission/search-v1/video';out.mkdir(parents=True,exist_ok=False)
    ledger=(ROOT/'.state/spend.json').read_bytes();captions=[];errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu','--renderer-process-limit=1'])
        context=browser.new_context(viewport={'width':1440,'height':1000},record_video_dir=str(out/'raw'),record_video_size={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));captured=time.monotonic()
        page.goto('http://127.0.0.1:8502/search',wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='Small patches. A measured role for AI.',exact=True)).to_be_visible(timeout=30000)
        expect(page.get_by_role('cell',name='zipcpu-spi-c1-c3-d9_d9',exact=True)).to_be_visible()
        start=time.monotonic();trim=start-captured
        def hold(text,seconds):
            begin=time.monotonic()-start;print(f'{begin:.1f}s: {text}',flush=True);page.wait_for_timeout(seconds*1000)
            captions.append((begin,time.monotonic()-start,text))
        def select(identity):
            page.get_by_test_id('stSelectbox').get_by_role('combobox').click();page.get_by_role('option',name=re.compile('^'+identity+' · ')).click()
        hold('RTLRefine: generate small source edits, let NVIDIA rank existing IDs, then check.\nActual recorded Nebius rankings; fresh no-model checks run in this video.',9)
        hold('Same pool, same eight-candidate cap, same two fixed starting candidates.\nStatic search: 3/9 trace passes. NVIDIA-prioritized: 4/9. Both controls: 2/2.',10)
        page.get_by_text('Inspect a search',exact=True).click();select('case_02')
        expect(page.get_by_text('Recorded outcome: SEARCH_EXHAUSTED',exact=True)).to_be_visible()
        hold('Static source-order search exhausts its eight checks in this SPI scenario.\nAll failed candidates remain in the record; no audit result changes the order.',10)
        page.get_by_text('nvidia_prioritized',exact=True).click()
        expect(page.get_by_text('Recorded outcome: ALL_SEALED_TRACES_PASS',exact=True)).to_be_visible()
        page.get_by_text('NVIDIA ranking and rationale (model explanation)',exact=True).click()
        hold('NVIDIA prioritizes byte-order options and reaches the selected edit on check seven.\nIt does not write RTL, invent candidates, or see candidate scores before ranking.',10)
        page.get_by_text('NVIDIA ranking and rationale (model explanation)',exact=True).click()
        page.get_by_role('button',name='Recheck selected source',exact=True).click()
        expect(page.get_by_role('heading',name='Fresh recheck',exact=True)).to_be_visible(timeout=90000)
        page.get_by_role('heading',name='Fresh recheck',exact=True).scroll_into_view_if_needed()
        hold('Fresh execution passes three fixed 522,559-cycle profiles.\nThe selected edit changes FIFO B only; FIFO A and all operating conditions are unverified.',13)
        with page.expect_download() as item:page.get_by_role('button',name='Download search evidence',exact=True).click()
        item.value.save_as(str(out/'selected-search-evidence.zip'))
        hold('Export generated sources, original inputs, frozen expected values,\nraw rankings, controller code, licenses and hashes. This is scoped trace agreement.',8)
        select('case_09');expect(page.get_by_text('Recorded outcome: AUDIT_FAILED',exact=True)).to_be_visible()
        expect(page.get_by_test_id('stMetric').filter(has_text='Published discovery trace')).to_have_count(1,timeout=30000)
        page.get_by_text('Recorded outcome: AUDIT_FAILED',exact=True).scroll_into_view_if_needed()
        hold('A partial reset edit passes discovery but fails both additional audits.\nBoth methods reject it without another candidate. Audit data never enters ranking.',11)
        page.get_by_text('Complete comparison',exact=True).click();page.get_by_role('heading',name='Small patches. A measured role for AI.',exact=True).scroll_into_view_if_needed()
        hold('Nine ranking calls, estimated $0.111, excluding local compute and added latency.\nKnown development cases; a one-case difference is not general superiority or a new algorithm.',11)
        duration=time.monotonic()-start;raw=Path(page.video.path());context.close();browser.close()
    assert not errors and ledger==(ROOT/'.state/spend.json').read_bytes() and duration<177
    (out/'captions.srt').write_text(''.join(f'{i}\n{stamp(a)} --> {stamp(b)}\n{t}\n\n' for i,(a,b,t) in enumerate(captions,1)))
    video=out/'RTLRefine-constrained-search-demo.mp4'
    filters="subtitles=captions.srt:force_style='FontName=DejaVu Sans,FontSize=17,Outline=1,Shadow=0,MarginV=16'"
    subprocess.run(['ffmpeg','-y','-ss',str(trim),'-i',str(raw),'-t',str(duration),'-vf',filters,'-an','-c:v','libx264','-threads','2','-preset','fast','-crf','21','-pix_fmt','yuv420p','-r','30','-movflags','+faststart',str(video)],cwd=out,check=True,capture_output=True)
    probe=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(video)],check=True,capture_output=True,text=True)
    seconds=float(json.loads(probe.stdout)['format']['duration']);assert seconds<180
    report={'status':'PASS','new_model_calls':0,'browser_errors':errors,'actual_UI_and_fresh_recheck':True,'model_ranking_not_source_generation_disclosed':True,
            'matched_candidate_caps_and_partial_lane_scope_disclosed':True,'audit_rejection_and_development_limits_disclosed':True,'video_seconds':seconds,'video_sha256':hashlib.sha256(video.read_bytes()).hexdigest()}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
