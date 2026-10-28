"""Record actual native runs and an explicitly labeled prior NVIDIA repair."""
import argparse
import hashlib
import io
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.record_submission_2026 import stamp,ass_stamp


def main():
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8543');p.add_argument('--output',default='submission/functional-v1');args=p.parse_args()
    out=ROOT/args.output;out.mkdir(exist_ok=True);video_dir=out/'video';video_dir.mkdir(exist_ok=False);screens=out/'screenshots';screens.mkdir(exist_ok=True)
    captions=[];errors=[];ledger=(ROOT/'.state/spend.json').read_bytes()
    recorded=json.loads((ROOT/'demo/functional_repair/simultaneous/run/result.json').read_text())
    with sync_playwright() as w:
        b=w.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu','--renderer-process-limit=1'])
        context=b.new_context(viewport={'width':1600,'height':800},record_video_dir=str(video_dir/'raw'),record_video_size={'width':1600,'height':800},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));captured=time.monotonic()
        page.goto(args.url+'/properties',wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='A passing test can still miss a bug.',exact=True)).to_be_visible(timeout=30000)
        expect(page.get_by_role('button',name='Repair from a counterexample with NVIDIA',exact=True)).to_be_disabled()
        start=time.monotonic();trim=start-captured
        def hold(text,seconds):
            begin=time.monotonic()-start;print(f'{begin:.1f}s: {text}',flush=True);page.wait_for_timeout(seconds*1000);captions.append((begin,time.monotonic()-start,text))
        def show():page.get_by_role('heading',name='Independent verification',exact=True).evaluate("e=>e.scrollIntoView({block:'start'})")
        hold('RTLRefine: repair RTL, export its checks, and catch the bug if it returns.\nThe NVIDIA result is a recorded actual run; native checks below run fresh.',7)
        page.get_by_role('button',name='Find hidden failures without NVIDIA',exact=True).click()
        expect(page.get_by_text('No checked export: INDEPENDENT_FAILURE_FOUND',exact=True)).to_be_visible(timeout=60000)
        show();hold('The original passes four smoke expectations. Independent checks find a hidden failure.\nIts public counterexample becomes a self-checking regression.',9)
        page.screenshot(path=str(screens/'01-original-regression-failure.png'))
        page.get_by_role('button',name='Run original failing regressions',exact=True).click()
        expect(page.get_by_text(re.compile(r'^Original bug reproduced · exit 1 · \d+ failing regression cases\. Zero model calls\.$'))).to_be_visible(timeout=30000)
        hold('Run the included Python script against the original: exit 1, both cases fail.\nExpectations come from the contract, never from the broken design output.',9)
        page.get_by_role('button',name='Show saved repair and evidence',exact=True).click()
        expect(page.get_by_text('Saved actual NVIDIA run',exact=True)).to_be_visible()
        page.get_by_test_id('stCode').filter(has_text='--- rtl/packet_queue.sv').evaluate("e=>e.scrollIntoView({block:'start'})")
        hold('Recorded actual Nemotron repair on Nebius: one request corrects the state update.\nThe selected file passes the original tests and fixed final bounds 16 and 20.',12)
        page.screenshot(path=str(screens/'02-exact-patch-and-final-checks.png'))
        page.get_by_test_id('stCode').filter(has_text='python3 -I rtlrefine_regressions/run.py').evaluate("e=>e.scrollIntoView({block:'center'})")
        page.get_by_role('button',name='Run standalone regressions without NVIDIA',exact=True).click()
        expect(page.get_by_text('Standalone regressions passed · exit 0 · 2/2 cases. Zero model calls.',exact=True)).to_be_visible(timeout=30000)
        hold('The checked export carries two regressions with 191 assertions.\nIts standalone runner returns exit 0, with no API key or application dependency.',10)
        with page.expect_download() as pending:page.get_by_role('button',name='Download property-checked project',exact=True).click()
        pending.value.save_as(str(video_dir/'checked-project.zip'))
        assert hashlib.sha256((video_dir/'checked-project.zip').read_bytes()).hexdigest()==recorded['checked_archive_sha256']
        page.get_by_text('Mapped resource comparison · synthesis estimate',exact=True).click()
        table=page.get_by_test_id('stTable').filter(has_text='Logic LUT cells');table.evaluate("e=>e.scrollIntoView({block:'center'})")
        hold('Same 7-series synthesis settings: logic LUT cells 12 to 11; registers and LUTRAM unchanged.\nThese are mapped estimates, not placement, timing, power or board measurements.',10)
        page.screenshot(path=str(screens/'03-mapped-resource-tradeoffs.png'))
        with zipfile.ZipFile(video_dir/'checked-project.zip') as archive:files={n:archive.read(n) for n in archive.namelist()}
        source='rtl/packet_queue.sv';old=files[source];files[source]=old.replace(b"2'b11: count <= count;",b"2'b11: count <= count + 1;")
        assert files[source]!=old
        bad=video_dir/'reintroduced-bug.zip'
        with zipfile.ZipFile(bad,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for n,data in files.items():z.writestr(n,data)
        page.locator('input[type=file]').set_input_files(str(bad))
        expect(page.get_by_role('button',name='Download property-checked project',exact=True)).to_have_count(0)
        hold('Reintroduce the original bug into the exported source. The prior acceptance disappears.\nThe retained tests remain unchanged and will run against a fresh source snapshot.',8)
        page.get_by_role('button',name='Find hidden failures without NVIDIA',exact=True).click()
        expect(page.get_by_text('No checked export: INDEPENDENT_FAILURE_FOUND',exact=True)).to_be_visible(timeout=60000)
        page.get_by_role('button',name='Run original failing regressions',exact=True).click()
        expect(page.get_by_text(re.compile(r'^Original bug reproduced · exit 1 · \d+ failing regression cases\. Zero model calls\.$'))).to_be_visible(timeout=30000)
        show();hold('The restored defect fails again: no checked download, exit 1.\nReopening through the general project route also retains the FIFO checks.',10)
        page.screenshot(path=str(screens/'04-bug-reintroduction-detected.png'))
        page.locator('input[type=file]').set_input_files(str(ROOT/'.tools/functional-browser-release/without-json.zip'))
        page.get_by_role('button',name='Inspect FIFO ports without NVIDIA',exact=True).click()
        expect(page.get_by_test_id('stSelectbox').filter(has_text='Contract port: clk')).to_be_visible(timeout=30000)
        page.get_by_test_id('stSelectbox').filter(has_text='Contract port: clk').evaluate("e=>e.scrollIntoView({block:'start'})")
        hold('Bring your own source and benches without writing JSON. Inspect actual DUT ports,\nmap signals and set capacity. Port inspection alone is not a correctness check.',12)
        page.screenshot(path=str(screens/'05-json-free-port-setup.png'))
        hold('The FIFO profile is bounded and synchronous; these examples are authored integration cases.\nSource, Docker build and evidence: github.com/ehdtjq08/RTLRefine',8)
        duration=time.monotonic()-start;raw=Path(page.video.path());context.close();b.close()
    assert not errors and duration<177 and ledger==(ROOT/'.state/spend.json').read_bytes()
    (video_dir/'captions.srt').write_text(''.join(f'{i}\n{stamp(a)} --> {stamp(b)}\n{text}\n\n' for i,(a,b,text) in enumerate(captions,1)))
    header=(ROOT/'submission/property-v1/video/captions.ass').read_text().split('[Events]')[0]
    events='[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
    (video_dir/'captions.ass').write_text(header+events+''.join(f'Dialogue: 0,{ass_stamp(a)},{ass_stamp(b)},Default,,0,0,0,,'+text.replace('\n',r'\N')+'\n' for a,b,text in captions))
    video=video_dir/'RTLRefine-functional-demo.mp4'
    subprocess.run(['ffmpeg','-y','-ss',str(trim),'-i',str(raw),'-t',str(duration),'-vf','scale=1920:960,pad=1920:1080:0:0:color=0x0b1117,ass=captions.ass','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','20','-pix_fmt','yuv420p','-r','30','-movflags','+faststart',str(video)],cwd=video_dir,check=True,capture_output=True)
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(video)],check=True,capture_output=True,text=True).stdout)
    seconds=float(probe['format']['duration']);assert seconds<180
    report={'status':'PASS','video_seconds':seconds,'video_sha256':hashlib.sha256(video.read_bytes()).hexdigest(),
            'actual_ui_and_native_runs':True,'recorded_nvidia_run_explicitly_labeled':True,'new_model_calls_during_recording':0,
            'recorded_actual_model_requests':recorded['api_requests'],'standalone_exit_zero_and_one_demonstrated':True,
            'json_free_setup_shown':True,'resource_scope_disclosed':True,'authored_bounded_scope_disclosed':True,
            'continuous_normal_speed_recording':True,'english_captions_in_separate_band':True,'browser_errors':errors,'youtube_uploaded':False}
    (video_dir/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
