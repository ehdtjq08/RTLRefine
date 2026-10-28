"""Append a clearly labeled normal-speed real-external-RTL segment to the demo."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scripts.record_submission_2026 import stamp,ass_stamp


def main():
    out=ROOT/'submission/external-v1';out.mkdir(exist_ok=True);video_dir=out/'video';video_dir.mkdir(exist_ok=False)
    screens=out/'screenshots';screens.mkdir(exist_ok=True);ledger=(ROOT/'.state/spend.json').read_bytes();captions=[];errors=[]
    with sync_playwright() as w:
        b=w.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu'])
        context=b.new_context(viewport={'width':1600,'height':800},record_video_dir=str(video_dir/'raw'),record_video_size={'width':1600,'height':800})
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));captured=time.monotonic()
        page.goto('http://127.0.0.1:8551/external-validation',wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='Validated on independently developed RTL.',exact=True)).to_be_visible(timeout=30000)
        start=time.monotonic();trim=start-captured
        def hold(text,seconds):
            a=time.monotonic()-start;page.wait_for_timeout(seconds*1000);captions.append((a,time.monotonic()-start,text))
        hold('External validation: a real upstream early-ready throughput regression.\nCommit-pinned verilog-axis source and its MIT license are retained.',7)
        page.get_by_test_id('stCode').evaluate("e=>e.scrollIntoView({block:'start'})")
        hold('Actual recorded NVIDIA repair: one request, then eight benches and 30,493 assertions.\nThis is a known upstream regression, not a new discovery or unseen accuracy.',10)
        page.screenshot(path=str(screens/'01-real-upstream-repair.png'))
        page.get_by_role('button',name='Recheck external NVIDIA repair without inference',exact=True).click()
        expect(page.get_by_text('Fresh external project recheck passed. Zero model requests.',exact=True)).to_be_visible(timeout=30000)
        hold('Fresh export reimport passes again without inference. The oracle is an independent\ntransaction scoreboard and skid-capacity requirement, not corrected reference RTL.',8)
        page.get_by_role('tab',name='Second-author healthy control',exact=True).click()
        panel=page.get_by_role('tabpanel',name='Second-author healthy control',exact=True)
        panel.get_by_role('heading',name='ZipCPU · skid buffer',exact=True).evaluate("e=>e.scrollIntoView({block:'start'})")
        hold('A second author: unmodified ZipCPU skidbuffer plus a disclosed stateless adapter.\nEight profiles and 30,847 assertions pass; zero model requests and no bug claim.',9)
        page.screenshot(path=str(screens/'02-second-author-control.png'))
        hold('Finite simulation at stated parameters, with legal backpressure and qualified data.\nSource, licenses, failures and importable ZIPs: github.com/ehdtjq08/RTLRefine',7)
        seconds=time.monotonic()-start;raw=Path(page.video.path());context.close();b.close()
    assert not errors and ledger==(ROOT/'.state/spend.json').read_bytes()
    (video_dir/'external-captions.srt').write_text(''.join(f'{i}\n{stamp(a)} --> {stamp(b)}\n{text}\n\n' for i,(a,b,text) in enumerate(captions,1)))
    header=(ROOT/'submission/functional-v1/video/captions.ass').read_text().split('[Events]')[0]
    events='[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
    (video_dir/'external-captions.ass').write_text(header+events+''.join(f'Dialogue: 0,{ass_stamp(a)},{ass_stamp(b)},Default,,0,0,0,,'+text.replace('\n',r'\N')+'\n' for a,b,text in captions))
    segment=video_dir/'external-segment.mp4'
    subprocess.run(['ffmpeg','-y','-ss',str(trim),'-i',str(raw),'-t',str(seconds),'-vf','scale=1920:960,pad=1920:1080:0:0:color=0x0b1117,ass=external-captions.ass','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','20','-pix_fmt','yuv420p','-r','30','-movflags','+faststart',str(segment)],cwd=video_dir,check=True,capture_output=True)
    base=ROOT/'submission/functional-v1/video/RTLRefine-functional-demo.mp4'
    (video_dir/'concat.txt').write_text("file '"+str(base)+"'\nfile '"+str(segment)+"'\n")
    final=video_dir/'RTLRefine-external-validation-demo.mp4'
    subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-i',str(video_dir/'concat.txt'),'-c','copy','-movflags','+faststart',str(final)],check=True,capture_output=True)
    def duration(path):return float(json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)],check=True,capture_output=True,text=True).stdout)['format']['duration'])
    total=duration(final);base_duration=duration(base);assert total<180
    # Separate subtitles include both normal-speed segments.
    source_srt=(ROOT/'submission/functional-v1/video/captions.srt').read_text().rstrip();count=len(__import__('re').findall(r'^\d+\n',source_srt,__import__('re').M))
    source_srt+='\n\n'+''.join(f'{count+i}\n{stamp(a+base_duration)} --> {stamp(min(b+base_duration,total))}\n{text}\n\n' for i,(a,b,text) in enumerate(captions,1))
    (video_dir/'captions.srt').write_text(source_srt)
    report={'status':'PASS','video_seconds':total,'video_sha256':hashlib.sha256(final.read_bytes()).hexdigest(),
            'normal_speed_ui_segments':2,'previous_functional_segment_preserved':True,'base_video_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),
            'new_model_calls_during_recording':0,'real_recorded_model_request_labeled':True,'external_known_regression_not_new_discovery':True,
            'second_author_unmodified_healthy_control_labeled':True,'source_license_and_finite_scope_disclosed':True,'browser_errors':errors,'youtube_uploaded':False}
    (video_dir/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
