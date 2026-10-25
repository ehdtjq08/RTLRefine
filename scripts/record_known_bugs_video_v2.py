"""Record corrected V2 scope, actual comparison and fresh regression checks."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def stamp(seconds):
    total=round(seconds*1000);hours,total=divmod(total,3600000);minutes,total=divmod(total,60000);seconds,total=divmod(total,1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{total:03}"


def main():
    output=ROOT/'submission/known-bugs-v2/video';output.mkdir(parents=True,exist_ok=False)
    ledger=(ROOT/'.state/spend.json').read_bytes();captions=[];errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu','--renderer-process-limit=1'])
        context=browser.new_context(viewport={'width':1440,'height':1000},record_video_dir=str(output/'raw'),record_video_size={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        captured=time.monotonic();page.goto('http://127.0.0.1:8502/benchmarks',wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='A fair test on known RTL bugs.',exact=True)).to_be_visible(timeout=30000)
        start=time.monotonic();trim=start-captured
        def hold(text,seconds):
            begin=time.monotonic()-start;print(f'{begin:.1f}s: {text}',flush=True)
            page.wait_for_timeout(seconds*1000);captions.append((begin,time.monotonic()-start,text))
        def select(identity):
            page.get_by_test_id('stSelectbox').get_by_role('combobox').click();page.get_by_role('option',name=re.compile('^'+identity+' · ')).click()
        hold('RTLRefine: V2: nine known historical RTL defects and two reference controls.\nReal recorded NVIDIA calls on Nebius; this video also runs fresh checks.',8)
        hold('Both methods share the first proposal and get at most two calls each.\nSelf-review: 1/9. Execution feedback: 2/9. One observed case difference, not general superiority.',10)
        page.get_by_text('Inspect and check a candidate',exact=True).click();select('case_08')
        expect(page.get_by_text('Recorded outcome: POLICY_REJECTED',exact=True)).to_be_visible()
        page.get_by_text('Recorded outcome: POLICY_REJECTED',exact=True).scroll_into_view_if_needed()
        hold('This self-review proposal violates the preserved source constraints.\nIts exact output and rejection remain recorded, along with all other failures.',12)
        page.get_by_text('checker_feedback',exact=True).click()
        expect(page.get_by_text('Recorded outcome: ALL_SEALED_TRACES_PASS',exact=True)).to_be_visible()
        page.get_by_text('Recorded outcome: ALL_SEALED_TRACES_PASS',exact=True).scroll_into_view_if_needed()
        hold('The same first proposal plus checking feedback produced an accepted change.\nThe model receives no corrected RTL or audit result; no functional manual fix is inserted.',8)
        page.get_by_text('Recorded model candidate',exact=True).click()
        page.get_by_role('button',name='Run sealed regression checks',exact=True).click()
        expect(page.get_by_role('button',name='Download current checked RTL',exact=True)).to_be_visible(timeout=90000)
        page.get_by_text('ALL SEALED TRACES PASS',exact=True).last.scroll_into_view_if_needed()
        hold('Fresh native checks reproduce the published trace and two additional audits.\nThis cohort uses corrected-control golden traces and two-state simulation, not unbounded proof.',14)
        with page.expect_download() as item:page.get_by_role('button',name='Download current-check evidence',exact=True).click()
        item.value.save_as(str(output/'fresh-case-evidence.zip'))
        hold('Download the exact checked source, frozen inputs and expected values,\nraw model evidence, compiler logs, vendor licenses and cryptographic hashes.',8)
        page.get_by_text('Oracle validity',exact=True).click()
        expect(page.get_by_role('heading',name='Supported oracle domain',exact=True)).to_be_visible()
        hold('V2 checks declared input domains, valid-qualified outputs and oracle assumptions.\nAn independent Python byte-count model qualifies the frame-length expectations.',8)
        page.get_by_text('V1 development correction',exact=True).click()
        hold('We withdrew a V1 interpretation that wrongly called a popcount improvement harmful.\nV2 was separately requalified and frozen before its model calls. V1 is retained.',8)
        page.get_by_text('Complete comparison',exact=True).click()
        page.get_by_role('heading',name='A fair test on known RTL bugs.',exact=True).scroll_into_view_if_needed()
        hold('29 actual requests, estimated $1.464. All seven cases failing both arms are retained.\nKnown public research versions, one trial per case; no unseen-accuracy or superiority claim.',12)
        duration=time.monotonic()-start;raw=Path(page.video.path());context.close();browser.close()
    assert not errors and ledger==(ROOT/'.state/spend.json').read_bytes()
    assert duration<177
    (output/'captions.srt').write_text(''.join(f'{i}\n{stamp(a)} --> {stamp(b)}\n{text}\n\n' for i,(a,b,text) in enumerate(captions,1)))
    video=output/'RTLRefine-known-bugs-v2-demo.mp4'
    filters="subtitles=captions.srt:force_style='FontName=DejaVu Sans,FontSize=17,Outline=1,Shadow=0,MarginV=16'"
    subprocess.run(['ffmpeg','-y','-ss',str(trim),'-i',str(raw),'-t',str(duration),'-vf',filters,'-an','-c:v','libx264','-threads','2','-preset','fast','-crf','21','-pix_fmt','yuv420p','-r','30','-movflags','+faststart',str(video)],cwd=output,check=True,capture_output=True)
    result=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(video)],check=True,text=True,capture_output=True)
    seconds=float(json.loads(result.stdout)['format']['duration']);assert seconds<180
    report={'status':'PASS','new_model_calls':0,'browser_errors':errors,'actual_UI_recorded':True,'recorded_real_Nebius_results':True,
            'fresh_checks_in_video':True,'golden_trace_scope_disclosed':True,'small_sample_and_negative_outcomes_disclosed':True,
            'video_seconds':seconds,'video_sha256':hashlib.sha256(video.read_bytes()).hexdigest()}
    (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
