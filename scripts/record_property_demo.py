"""Record one live FIFO repair and fresh export verification without speeding it up."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

from playwright.sync_api import expect,sync_playwright

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from rtl_agent.budget import BudgetLedger
from scripts.record_submission_2026 import stamp,ass_stamp


def main():
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8522');p.add_argument('--output',default='submission/property-v1');args=p.parse_args()
    out=ROOT/args.output;out.mkdir(exist_ok=True);video_dir=out/'video';video_dir.mkdir(exist_ok=False)
    screens=out/'screenshots';screens.mkdir(exist_ok=True);captions=[];errors=[]
    budget=BudgetLedger().summary()
    with sync_playwright() as w:
        b=w.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu','--renderer-process-limit=1'])
        context=b.new_context(viewport={'width':1600,'height':800},record_video_dir=str(video_dir/'raw'),record_video_size={'width':1600,'height':800},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        captured=time.monotonic();page.goto(args.url+'/properties',wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='A passing test can still miss a bug.',exact=True)).to_be_visible(timeout=30000)
        page.get_by_role('button',name='Find hidden failures without NVIDIA',exact=True).click()
        expect(page.get_by_text('No checked export: INDEPENDENT_FAILURE_FOUND',exact=True)).to_be_visible(timeout=60000)
        page.get_by_role('heading',name='A passing test can still miss a bug.',exact=True).evaluate("e=>e.scrollIntoView({block:'start'})")
        start=time.monotonic();trim=start-captured;pending=None
        def hold(text,seconds):
            nonlocal pending
            begin=time.monotonic()-start;print(f'{begin:.1f}s: {text}',flush=True)
            page.wait_for_timeout(seconds*1000);end=time.monotonic()-start
            if pending:
                a,action_end,action_text=pending;split=min(end,max(action_end,a+min(6,(end-a)/2)))
                captions.append((a,split,action_text));begin=split;pending=None
            captions.append((begin,end,text))
        def action(text,run):
            nonlocal pending
            a=time.monotonic()-start;run();pending=(a,time.monotonic()-start,text)
        def show():page.get_by_role('heading',name='Independent verification',exact=True).evaluate("e=>e.scrollIntoView({block:'start'})")
        hold('A FIFO smoke test passes, yet the design still produces a ghost output.\nRTLRefine finds and replays the hidden failure before asking NVIDIA.',7)
        show()
        hold('This authored FIFO passes all four smoke expectations.\nAn independent contract finds a failure in five symbolic clock states.',9)
        page.screenshot(path=str(screens/'01-smoke-pass-independent-failure.png'))
        hold('After the accepted words have left, output-valid remains asserted.\nThe SAT inputs reproduce this in Icarus against a separate Python queue.',9)
        def live():
            page.get_by_role('button',name='Repair from a counterexample with NVIDIA',exact=True).click()
            expect(page.get_by_text('The exact project passed tests, bounded properties and progress checks.',exact=True)).to_be_visible(timeout=100000)
        action('A real NVIDIA Nemotron request through Nebius Token Factory.\nPublic source, contract and replay guide repair; final audit results stay hidden.',live)
        show()
        hold('Nemotron fixes occupancy when enqueue and dequeue happen together.\nThe exact source passes the supplied tests and final bounds 16 and 20.',12)
        page.screenshot(path=str(screens/'02-nvidia-exact-patch.png'))
        with page.expect_download() as pending_download:page.get_by_role('button',name='Download property-checked project',exact=True).click()
        pending_download.value.save_as(str(video_dir/'property-checked-project.zip'))
        with page.expect_download() as pending_download:page.get_by_role('button',name='Download property evidence',exact=True).click()
        pending_download.value.save_as(str(video_dir/'live-property-evidence.zip'))
        with zipfile.ZipFile(video_dir/'live-property-evidence.zip') as archive:live_record=json.loads(archive.read('result.json'))
        assert live_record['accepted'] and 1<=live_record['api_requests']<=2
        assert hashlib.sha256((video_dir/'property-checked-project.zip').read_bytes()).hexdigest()==live_record['checked_archive_sha256']
        def recheck():
            page.get_by_role('button',name='Recheck exported project without NVIDIA',exact=True).click()
            expect(page.get_by_text('Exported ZIP passed a fresh independent recheck. Zero model requests.',exact=True)).to_be_visible(timeout=120000)
        action('Reimport and rebuild the downloaded ZIP with no new model request.\nThe same fixed tests, bounded properties and progress checks run again.',recheck)
        hold('The export passes again. Evidence includes source hashes and tool logs.\nProgress checks exercise full, stalled, overlapping, wrapped and reset traffic.',8)
        page.get_by_text('Independent FIFO contract · fixed before the run',exact=True).click()
        field=page.get_by_role('textbox',name='Contract JSON',exact=True)
        c=json.loads(field.input_value());c['data_width']=8;field.fill(json.dumps(c,indent=2));field.press('Tab')
        expect(page.get_by_role('button',name='Download property-checked project',exact=True)).to_have_count(0)
        hold('Change the contract: the old acceptance and checked download disappear.\nA successful verdict is tied to the exact source and configuration.',8)
        page.get_by_role('button',name='Find hidden failures without NVIDIA',exact=True).click()
        expect(page.get_by_text('No checked export: PROPERTY_SETUP_REQUIRED',exact=True)).to_be_visible(timeout=60000)
        show();hold('The declared eight-bit width disagrees with the four-bit DUT.\nIt is rejected before any paid diagnosis.',7)
        page.screenshot(path=str(screens/'03-changed-contract-rejected.png'))
        page.get_by_test_id('stSelectbox').filter(has_text='Authored FIFO integration example').get_by_role('combobox').click()
        page.get_by_role('option',name='Read pointer wraps too early',exact=True).click()
        expect(page.get_by_text('No checked export: INDEPENDENT_FAILURE_FOUND',exact=True)).to_be_visible(timeout=30000)
        show();hold('A second authored defect passes its smoke test too.\nIndependent checks reproduce its premature pointer wrap in six states.',8)
        page.screenshot(path=str(screens/'04-second-defect.png'))
        page.get_by_test_id('stSelectbox').filter(has_text='Authored FIFO integration example').get_by_role('combobox').click()
        page.get_by_role('option',name='Healthy FIFO control',exact=True).click()
        expect(page.get_by_text('The exact project passed tests, bounded properties and progress checks.',exact=True)).to_be_visible(timeout=30000)
        show();hold('The healthy control passes without asking the model for a repair.\nThese are authored integration cases, not an unseen repair-accuracy benchmark.',8)
        hold('Upload projects at /project; use /properties for the stated FIFO contract.\nPublic source and Docker test build: github.com/ehdtjq08/RTLRefine',7)
        seconds=time.monotonic()-start;raw=Path(page.video.path());context.close();b.close()
    assert not errors and seconds<177,(errors,seconds)
    after=BudgetLedger().summary();assert after['requests']-budget['requests']==live_record['api_requests']
    (video_dir/'captions.srt').write_text(''.join(f'{i}\n{stamp(a)} --> {stamp(b)}\n{text}\n\n' for i,(a,b,text) in enumerate(captions,1)))
    header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,28,&H00F4F1EB,&H00F4F1EB,&H000B1117,&H000B1117,0,0,0,0,100,100,0,0,1,0,0,2,70,70,22,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    (video_dir/'captions.ass').write_text(header+''.join(f'Dialogue: 0,{ass_stamp(a)},{ass_stamp(b)},Default,,0,0,0,,'+text.replace('\n',r'\N')+'\n' for a,b,text in captions))
    video=video_dir/'RTLRefine-independent-properties-demo.mp4'
    subprocess.run(['ffmpeg','-y','-ss',str(trim),'-i',str(raw),'-t',str(seconds),'-vf','scale=1920:960,pad=1920:1080:0:0:color=0x0b1117,ass=captions.ass','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','20','-pix_fmt','yuv420p','-r','30','-movflags','+faststart',str(video)],cwd=video_dir,check=True,capture_output=True)
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(video)],check=True,capture_output=True,text=True).stdout)
    duration=float(probe['format']['duration']);assert duration<180
    report={'status':'PASS','video_seconds':duration,'video_sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'actual_ui_recorded':True,'continuous_real_time':True,
            'english_captions_in_separate_band':True,'new_model_calls':live_record['api_requests'],'actual_model_run_directory':live_record['directory'],
            'new_model_estimated_cost_usd':round(after['accounted_usd']-budget['accounted_usd'],6),'fresh_export_recheck':True,'stale_verdict_hidden_on_contract_change':True,
            'authored_cases_labeled':True,'bounded_scope_disclosed':True,'youtube_upload_complete':False,'browser_errors':errors}
    (video_dir/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
