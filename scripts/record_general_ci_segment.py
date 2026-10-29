"""Append a short normal-speed fresh-check/export segment, keeping total <3 min."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.record_submission_2026 import stamp, ass_stamp


def duration(path):
    return float(json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(path)], check=True, capture_output=True, text=True).stdout)['format']['duration'])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url', default='http://127.0.0.1:8554')
    a = p.parse_args()
    out = ROOT / 'submission/ci-v1'
    video = out / 'video'
    video.mkdir(parents=True, exist_ok=False)
    screens = out / 'screenshots'
    screens.mkdir(exist_ok=True)
    ledger = (ROOT / '.state/spend.json').read_bytes()
    captions, errors = [], []
    with sync_playwright() as w:
        browser = w.chromium.launch(executable_path=shutil.which('google-chrome'), headless=True, args=['--disable-dev-shm-usage', '--disable-gpu'])
        context = browser.new_context(viewport={'width': 1600, 'height': 800}, record_video_dir=str(video / 'raw'), record_video_size={'width': 1600, 'height': 800})
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        captured = time.monotonic()
        page.goto(a.url + '/project', wait_until='domcontentloaded')
        page.locator('input[type=file]').set_input_files(str(ROOT / 'demo/general_project_ci/axis-register/checked-project.zip'))
        expect(page.get_by_role('button', name='Check this project', exact=True)).to_be_visible()
        start = time.monotonic()
        trim = start - captured
        page.get_by_role('button', name='Check this project', exact=True).click()
        expect(page.get_by_text('The exact exported CI runner also passed. No model request.', exact=True)).to_be_visible(timeout=60000)
        page.get_by_text('The exact exported CI runner also passed. No model request.', exact=True).scroll_into_view_if_needed()

        def hold(text, seconds):
            t = time.monotonic() - start
            page.wait_for_timeout(seconds * 1000)
            captions.append((t, time.monotonic() - start, text))

        hold('Fresh general-project check: the exact exported standalone runner passes too.\nNo app installation or API key is needed to rerun its bundled tests.', 7)
        page.screenshot(path=str(screens / '01-general-project-ci-gate.png'))
        with page.expect_download() as pending:
            page.get_by_role('button', name='Download checked project ZIP', exact=True).click()
        pending.value.save_as(str(video / 'checked-project.zip'))
        page.get_by_text('Included GitHub Actions workflow', exact=True).click()
        page.get_by_role('button', name='Download CI workflow', exact=True).scroll_into_view_if_needed()
        hold('The same ZIP includes a GitHub Actions workflow and JSON/JUnit reports.\nPushes and pull requests recompile current RTL; inference is never requested.', 8)
        page.screenshot(path=str(screens / '02-exported-actions-workflow.png'))
        hold('Finite provided-test regression checking. Source edits require a fresh pass;\nprotected test/configuration edits require review and re-export.', 5)
        seconds = time.monotonic() - start
        raw = Path(page.video.path())
        context.close()
        browser.close()
    assert not errors and ledger == (ROOT / '.state/spend.json').read_bytes()
    header = (ROOT / 'submission/functional-v1/video/captions.ass').read_text().split('[Events]')[0]
    events = '[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
    (video / 'ci-captions.ass').write_text(header + events + ''.join(f'Dialogue: 0,{ass_stamp(t)},{ass_stamp(end)},Default,,0,0,0,,' + text.replace('\n', r'\N') + '\n' for t, end, text in captions))
    segment = video / 'ci-segment.mp4'
    subprocess.run(['ffmpeg', '-y', '-ss', str(trim), '-i', str(raw), '-t', str(seconds), '-vf', 'scale=1920:960,pad=1920:1080:0:0:color=0x0b1117,ass=ci-captions.ass', '-an', '-c:v', 'libx264', '-threads', '2', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', '30', '-movflags', '+faststart', str(segment)], cwd=video, check=True, capture_output=True)
    base = ROOT / 'submission/external-v1/video/RTLRefine-external-validation-demo.mp4'
    (video / 'concat.txt').write_text("file '" + str(base) + "'\nfile '" + str(segment) + "'\n")
    final = video / 'RTLRefine-project-ci-demo.mp4'
    subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(video / 'concat.txt'), '-c', 'copy', '-movflags', '+faststart', str(final)], check=True, capture_output=True)
    total, offset = duration(final), duration(base)
    assert total < 180, total
    srt = (ROOT / 'submission/external-v1/video/captions.srt').read_text().rstrip()
    count = len(re.findall(r'^\d+\n', srt, re.M))
    srt += '\n\n' + ''.join(f'{count + i}\n{stamp(t + offset)} --> {stamp(min(end + offset, total))}\n{text}\n\n' for i, (t, end, text) in enumerate(captions, 1))
    (video / 'captions.srt').write_text(srt.rstrip() + '\n')
    report = {'status': 'PASS', 'video_seconds': total, 'video_sha256': hashlib.sha256(final.read_bytes()).hexdigest(),
              'normal_speed_ui_segments': 3, 'prior_segments_preserved': True, 'base_video_sha256': hashlib.sha256(base.read_bytes()).hexdigest(),
              'new_model_calls_during_recording': 0, 'fresh_export_download_recorded': True, 'browser_errors': errors, 'youtube_uploaded': False}
    (video / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
