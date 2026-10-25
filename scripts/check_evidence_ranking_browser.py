"""Exercise ranking evidence, recorded replay and a fresh native recheck."""
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
    p=argparse.ArgumentParser();p.add_argument('--output',default='.tools/evidence-ranking-browser-qa');args=p.parse_args()
    out=ROOT/args.output;out.mkdir(exist_ok=False);before=(ROOT/'.state/spend.json').read_bytes();errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu','--renderer-process-limit=1'])
        page=browser.new_page(viewport={'width':1440,'height':1080},accept_downloads=True)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8502/ranking',wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='Spend the next RTL check where the evidence points.',exact=True)).to_be_visible(timeout=30000)
        for label,value in [('Circuit evidence · trace passes','6/10'),('Stability-gated order · trace passes','7 / 10'),('Uniform random · expected passes','3.33 / 10')]:
            expect(page.get_by_test_id('stMetric').filter(has_text=label).get_by_test_id('stMetricValue')).to_have_text(value)
        expect(page.get_by_text('The strongest simple baseline passes 7/10.',exact=False)).to_be_visible()
        expect(page.get_by_text('Each candidate pool is seeded with the known inverse.',exact=False)).to_be_visible()
        page.screenshot(path=str(out/'01_complete_comparison.png'))
        page.get_by_text('Inspect priorities',exact=True).click()
        def select(label,option):
            box=page.get_by_test_id('stSelectbox').filter(has_text=label).get_by_role('combobox')
            box.click();page.get_by_role('option',name=option).click()
        select('Ranking case',re.compile('^holdout_02 · '))
        select('Ranking method','Stability-gated NVIDIA + circuit evidence')
        expect(page.get_by_test_id('stMetric').filter(has_text='Gate decision').get_by_test_id('stMetricValue')).to_have_text('Use model order')
        expect(page.get_by_text('Machine-attached evidence',exact=True)).to_be_visible()
        expect(page.get_by_text('Model mechanism hypotheses · unverified',exact=True)).to_be_visible()
        page.get_by_role('button',name='Replay recorded eight-check budget',exact=True).click()
        expect(page.get_by_text('Recorded outcome replay · no new simulation or API request',exact=True)).to_be_visible()
        page.get_by_role('button',name='Run fresh isolated checks on this patch',exact=True).click()
        expect(page.get_by_text('Fresh check: all three fixed traces passed.',exact=True)).to_be_visible(timeout=90000)
        expect(page.get_by_text('Checked source SHA-256: bdfb4e29768c5224c543098765b8d648f3fe774eb42643c289d85b446414d155',exact=True)).to_be_visible()
        page.get_by_text('Machine-attached evidence',exact=True).scroll_into_view_if_needed()
        page.screenshot(path=str(out/'02_machine_provenance.png'))
        with page.expect_download() as pending:page.get_by_role('button',name='Download case ranking evidence',exact=True).click()
        pending.value.save_as(str(out/'ranking-evidence.zip'))
        with zipfile.ZipFile(out/'ranking-evidence.zip') as archive:
            manifest=json.loads(archive.read('manifest.json'))
            assert len(manifest)+1==len(archive.namelist())
            for name,digest in manifest.items():assert hashlib.sha256(archive.read(name)).hexdigest()==digest
            assert 'source_license/LICENSE' in manifest or 'source_license/COPYING' in manifest
            assert 'inputs/holdout_02/pool.json' in manifest
            assert not any('.env' in name or 'obj_dir' in name for name in manifest)
        # An unstable model order is visibly replaced, without another paid call.
        select('Ranking case',re.compile('^holdout_01 · '))
        expect(page.get_by_test_id('stMetric').filter(has_text='Gate decision').get_by_test_id('stMetricValue')).to_have_text('Use circuit heuristic')
        page.get_by_test_id('stMetric').filter(has_text='Gate decision').scroll_into_view_if_needed()
        page.screenshot(path=str(out/'03_unstable_order_deferred.png'))
        browser.close()
    assert not errors and before==(ROOT/'.state/spend.json').read_bytes()
    result={'status':'PASS','new_model_calls':0,'browser_errors':errors,'strong_baseline_tie_visible':True,
        'synthetic_seeded_pool_scope_visible':True,'machine_evidence_and_unverified_claims_separate':True,
        'recorded_replay_and_fresh_native_check_distinct':True,'fresh_check_source_hash_verified':True,
        'download_manifest_and_license_verified':True,'stability_fallback_visible':True}
    (out/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
