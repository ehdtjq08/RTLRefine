"""Append a normal-speed recorded-result close-up, without another model call."""
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import time

from playwright.sync_api import expect,sync_playwright

ROOT=Path(__file__).resolve().parent.parent


def append_captions(video_dir,start,end):
    def seconds(s):
        h,m,v=s.replace(',','.').split(':');return int(h)*3600+int(m)*60+float(v)
    def stamp(value,ass=False):
        value=round(value*(100 if ass else 1000));base=100 if ass else 1000
        h,value=divmod(value,3600*base);m,value=divmod(value,60*base);s,f=divmod(value,base)
        return f'{h}:{m:02}:{s:02}.{f:02}' if ass else f'{h:02}:{m:02}:{s:02},{f:03}'
    text='Patch close-up: simultaneous push and pop leave occupancy unchanged.\nThe exact exported file passes the fixed final bounds and progress check.'
    srt=(video_dir/'captions.srt').read_text()
    srt=re.sub(r'(\d\d:\d\d:\d\d,\d{3}) --> (\d\d:\d\d:\d\d,\d{3})',lambda m:m[1]+' --> '+stamp(min(seconds(m[2]),start)),srt)
    count=len(re.findall(r'^\d+\n',srt,re.M))
    (video_dir/'captions.srt').write_text(srt.rstrip()+f'\n\n{count+1}\n{stamp(start)} --> {stamp(end)}\n{text}\n\n')
    lines=(video_dir/'captions.ass').read_text().splitlines()
    for i,line in enumerate(lines):
        if line.startswith('Dialogue:'):
            parts=line.split(',',9);parts[2]=stamp(min(seconds(parts[2]),start),True);lines[i]=','.join(parts)
    lines.append(f'Dialogue: 0,{stamp(start,True)},{stamp(end,True)},Default,,0,0,0,,'+text.replace('\n',r'\N'))
    (video_dir/'captions.ass').write_text('\n'.join(lines)+'\n')


def main():
    video_dir=ROOT/'submission/property-v1/video';work=ROOT/'.tools/property-video-closeup';work.mkdir(exist_ok=False)
    ledger=(ROOT/'.state/spend.json').read_bytes();source=video_dir/'RTLRefine-independent-properties-demo.mp4'
    with sync_playwright() as w:
        b=w.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu'])
        context=b.new_context(viewport={'width':1600,'height':800},record_video_dir=str(work/'raw'),record_video_size={'width':1600,'height':800})
        page=context.new_page();captured=time.monotonic();page.goto('http://127.0.0.1:8521/properties',wait_until='domcontentloaded')
        expect(page.get_by_text('The exact project passed tests, bounded properties and progress checks.',exact=True)).to_be_visible(timeout=30000)
        page.get_by_test_id('stCode').last.evaluate("e=>e.scrollIntoView({block:'start'})")
        trim=time.monotonic()-captured
        page.wait_for_timeout(10000)
        page.screenshot(path=str(ROOT/'submission/property-v1/screenshots/05-exact-count-fix-and-bounds.png'))
        raw=Path(page.video.path());context.close();b.close()
    assert ledger==(ROOT/'.state/spend.json').read_bytes()
    header=(video_dir/'captions.ass').read_text().split('[Events]')[0]
    text='Patch close-up: simultaneous push and pop leave occupancy unchanged.\\NThe exact exported file passes the fixed final bounds and progress check.'
    (work/'closeup.ass').write_text(header+'[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:00.00,0:00:08.00,Default,,0,0,0,,'+text+'\n')
    clip=work/'closeup.mp4'
    subprocess.run(['ffmpeg','-y','-ss',str(trim),'-i',str(raw),'-t','8','-vf','scale=1920:960,pad=1920:1080:0:0:color=0x0b1117,ass=closeup.ass',
                    '-an','-c:v','libx264','-threads','2','-preset','fast','-crf','20','-pix_fmt','yuv420p','-r','30','-movflags','+faststart',str(clip)],cwd=work,check=True,capture_output=True)
    original=work/'original-continuous-recording.mp4';shutil.copyfile(source,original)
    (work/'concat.txt').write_text("file '"+str(original)+"'\nfile '"+str(clip)+"'\n")
    combined=work/'combined.mp4'
    subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-i',str(work/'concat.txt'),'-c','copy','-movflags','+faststart',str(combined)],check=True,capture_output=True)
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(combined)],check=True,capture_output=True,text=True).stdout)
    duration=float(probe['format']['duration']);assert duration<180
    source.write_bytes(combined.read_bytes())
    report=json.loads((video_dir/'validation.json').read_text())
    append_captions(video_dir,report['video_seconds'],duration)
    report.update(video_seconds=duration,video_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),continuous_real_time=False,
                  normal_speed_ui_segments=2,live_run_segment_unchanged=True,original_continuous_video_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
                  same_result_patch_closeup_added=True,closeup_model_calls=0)
    (video_dir/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
