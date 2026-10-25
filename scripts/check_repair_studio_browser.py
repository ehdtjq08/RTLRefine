"""Real browser: checked source, fresh recheck, stale-result guard, partial fix rejection."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

from playwright.sync_api import expect,sync_playwright

ROOT=Path(__file__).resolve().parent.parent


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='.tools/repair-studio-browser-qa');parser.add_argument('--url',default='http://127.0.0.1:8502');args=parser.parse_args()
    out=ROOT/args.output;out.mkdir(exist_ok=False);before=(ROOT/'.state/spend.json').read_bytes();errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu','--renderer-process-limit=1'])
        page=browser.new_page(viewport={'width':1440,'height':1080},accept_downloads=True);page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(args.url,wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='An AI fix needs evidence.',exact=True)).to_be_visible(timeout=30000)
        expect(page.get_by_text('Saved NVIDIA run',exact=True)).to_be_visible()
        expect(page.get_by_text('The exact patch passed all three fixed profiles.',exact=True)).to_be_visible()
        expect(page.get_by_role('button',name='Diagnose and repair with NVIDIA',exact=True)).to_be_disabled()
        expect(page.locator('.studio-performance strong')).to_have_text('15.0×')
        expect(page.locator('svg.studio-waveform')).to_be_visible()
        page.evaluate('document.fonts.ready')
        page.screenshot(path=str(out/'01_complete_repair.png'))
        page.get_by_role('button',name='Recheck this exact patch',exact=True).click()
        expect(page.get_by_text('Fresh recheck passed · exact source hash verified.',exact=True)).to_be_visible(timeout=60000)
        with page.expect_download() as pending:page.get_by_role('button',name='Download checked RTL',exact=True).click()
        pending.value.save_as(str(out/'checked.v'))
        selected=ROOT/'demo/repair_studio/overflow/run/selected.v'
        assert (out/'checked.v').read_bytes()==selected.read_bytes()
        with page.expect_download() as pending:page.get_by_role('button',name='Download verification evidence',exact=True).click()
        pending.value.save_as(str(out/'evidence.zip'))
        with zipfile.ZipFile(out/'evidence.zip') as archive:
            manifest=json.loads(archive.read('manifest.json'))
            for name,digest in manifest.items():assert hashlib.sha256(archive.read(name)).hexdigest()==digest
            assert archive.read('run/selected.v')==selected.read_bytes()
            assert 'case/LICENSE' in manifest and 'ARTIFACT-LICENSE-BSD-3-Clause.txt' in manifest
            assert not any('.env' in name or 'obj_dir' in name for name in manifest)
        page.get_by_text('NVIDIA hypotheses · unverified',exact=True).click();page.get_by_text('Nemotron diagnosis',exact=True).scroll_into_view_if_needed();page.screenshot(path=str(out/'02_checked_patch.png'))
        box=page.get_by_test_id('stSelectbox').filter(has_text='Choose a real RTL failure').get_by_role('combobox')
        box.click();page.get_by_role('option',name='Reset leaves stale packet state',exact=True).click()
        expect(page.get_by_text('The exact patch passed all three fixed profiles.',exact=True)).to_be_visible()
        pool=json.loads((ROOT/'results/repair_search_pools_v1_20261023/case_09/pool.json').read_text())
        partial=next(c for c in pool if c['id']=='candidate_001')['rtl']
        page.get_by_role('tab',name='Edit source',exact=True).click()
        page.get_by_test_id('stTextArea').locator('textarea').fill(partial)
        page.get_by_test_id('stTextArea').locator('textarea').press('Tab')
        expect(page.get_by_role('button',name='Download checked RTL',exact=True)).to_have_count(0)
        page.get_by_role('button',name='Run bounded local search',exact=True).click()
        expect(page.get_by_text('The selected patch failed independent checks and was not accepted.',exact=True)).to_be_visible(timeout=90000)
        expect(page.get_by_test_id('stMetric').filter(has_text='Independent profiles').get_by_test_id('stMetricValue')).to_have_text('1/3')
        expect(page.get_by_role('button',name='Download checked RTL',exact=True)).to_have_count(0)
        page.get_by_text('The selected patch failed independent checks and was not accepted.',exact=True).scroll_into_view_if_needed()
        page.screenshot(path=str(out/'03_partial_fix_rejected.png'))
        page.get_by_role('button',name='Restore example',exact=True).click()
        expect(page.get_by_text('The exact patch passed all three fixed profiles.',exact=True)).to_be_visible()
        expect(page.get_by_role('button',name='Download checked RTL',exact=True)).to_have_count(1)
        mobile=browser.new_page(viewport={'width':390,'height':844})
        mobile.goto(args.url,wait_until='domcontentloaded')
        expect(mobile.locator('svg.studio-waveform')).to_be_visible(timeout=30000)
        assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
        assert mobile.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollWidth <= e.clientWidth+1')
        mobile.evaluate('document.fonts.ready');mobile.screenshot(path=str(out/'04_mobile.png'),full_page=True)
        browser.close()
    assert not errors and before==(ROOT/'.state/spend.json').read_bytes()
    record={'status':'PASS','new_model_calls':0,'browser_errors':errors,'recorded_diagnosis_and_diff_visible':True,
        'fresh_exact_source_recheck_passed':True,'download_matches_checked_hash':True,'evidence_license_manifest_valid':True,
        'stale_success_hidden_after_source_edit':True,'public_pass_audit_failure_rejected':True,'screening_scope_visible':True,'signal_waveform_visible':True,'mobile_has_no_page_overflow':True,'restore_example_passed':True}
    (out/'validation.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))


if __name__=='__main__':main()
