"""No-model browser verification of the same-pool search evidence."""
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
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='.tools/repair-search-browser-qa');args=parser.parse_args()
    out=ROOT/args.output;out.mkdir(exist_ok=False);before=(ROOT/'.state/spend.json').read_bytes();errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu','--renderer-process-limit=1'])
        page=browser.new_page(viewport={'width':1440,'height':1100},accept_downloads=True);page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8502/search',wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='Small patches. A measured role for AI.',exact=True)).to_be_visible(timeout=30000)
        for label,value in [('Static-search trace passes','3/9'),('NVIDIA-prioritized trace passes','4/9'),('NVIDIA ranking calls','9')]:
            expect(page.get_by_test_id('stMetric').filter(has_text=label).get_by_test_id('stMetricValue')).to_have_text(value)
        expect(page.get_by_role('cell',name='zipcpu-spi-c1-c3-d9_d9',exact=True)).to_be_visible()
        page.screenshot(path=str(out/'01_matched_search.png'))
        page.get_by_text('Inspect a search',exact=True).click()
        def select(identity):
            page.get_by_test_id('stSelectbox').get_by_role('combobox').click();page.get_by_role('option',name=re.compile('^'+identity+' · ')).click()
        select('case_02');page.get_by_text('nvidia_prioritized',exact=True).click()
        expect(page.get_by_text('Recorded outcome: ALL_SEALED_TRACES_PASS',exact=True)).to_be_visible()
        expect(page.get_by_text('Coverage limit: this selected edit changes FIFO B byte order only.',exact=False)).to_be_visible()
        page.get_by_role('button',name='Recheck selected source',exact=True).click()
        expect(page.get_by_role('heading',name='Fresh recheck',exact=True)).to_be_visible(timeout=90000)
        source=(ROOT/'demo/repair_search/run/case_02/candidate_014/candidate.v').read_bytes()
        with page.expect_download() as item:page.get_by_role('button',name='Download current checked RTL',exact=True).click()
        item.value.save_as(str(out/'checked.v'));assert (out/'checked.v').read_bytes()==source
        with page.expect_download() as item:page.get_by_role('button',name='Download search evidence',exact=True).click()
        item.value.save_as(str(out/'evidence.zip'))
        with zipfile.ZipFile(out/'evidence.zip') as archive:
            manifest=json.loads(archive.read('manifest.json'))
            assert len(manifest)+1==len(archive.namelist())
            for name,entry in manifest.items():assert hashlib.sha256(archive.read(name)).hexdigest()==entry['sha256']
            assert archive.read('record/candidate_014/candidate.v')==source
            assert 'record/ranking_response.json' in manifest and 'prepared_pool/pool.json' in manifest
            assert 'sealed_case/LICENSE' in manifest and 'ARTIFACT-LICENSE-BSD-3-Clause.txt' in manifest
            assert 'controller_source/rtl_agent__repair_search__candidates.py' in manifest
            assert not any('obj_dir' in n or '.env' in n for n in manifest)
        page.get_by_role('heading',name='Fresh recheck',exact=True).scroll_into_view_if_needed();page.screenshot(path=str(out/'02_guided_scope_recheck.png'))
        select('case_09')
        expect(page.get_by_text('Recorded outcome: AUDIT_FAILED',exact=True)).to_be_visible()
        expect(page.get_by_test_id('stMetric').filter(has_text='Published discovery trace')).to_have_count(1,timeout=30000)
        expect(page.get_by_test_id('stMetric').filter(has_text='Published discovery trace').get_by_test_id('stMetricValue')).to_have_text('Pass')
        expect(page.get_by_test_id('stMetric').filter(has_text='Additional audit traces').get_by_test_id('stMetricValue')).to_have_text('0/2')
        page.screenshot(path=str(out/'03_partial_reset_rejected.png'));browser.close()
    assert not errors and before==(ROOT/'.state/spend.json').read_bytes()
    result={'status':'PASS','new_model_calls':0,'browser_errors':errors,'matched_metrics_verified':True,'selected_source_recheck_passed':True,
            'exact_source_download':True,'pool_plan_controller_and_license_manifest_verified':True,'partial_lane_scope_visible':True,
            'public_pass_audit_rejection_visible':True}
    (out/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
