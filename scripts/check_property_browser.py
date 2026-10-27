"""Validate the current FIFO UI, exact export, stale-result hiding and zero cost."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from playwright.sync_api import expect,sync_playwright

ROOT=Path(__file__).resolve().parent.parent


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8521');parser.add_argument('--output',default='.tools/property-browser-final');args=parser.parse_args()
    out=ROOT/args.output;out.mkdir(exist_ok=False);errors=[]
    ledger=(ROOT/'.state/spend.json').read_bytes()
    record=json.loads((ROOT/'demo/property_repair/simultaneous/run/result.json').read_text())
    with sync_playwright() as w:
        b=w.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu'])
        page=b.new_page(viewport={'width':1600,'height':1000},accept_downloads=True);page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(args.url+'/properties',wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='A passing test can still miss a bug.',exact=True)).to_be_visible(timeout=30000)
        expect(page.get_by_text('Saved actual NVIDIA run',exact=True)).to_be_visible()
        expect(page.get_by_role('button',name='Repair from a counterexample with NVIDIA',exact=True)).to_be_disabled()
        expect(page.get_by_text('The exact project passed tests, bounded properties and progress checks.',exact=True)).to_be_visible()
        with page.expect_download() as pending:page.get_by_role('button',name='Download property-checked project',exact=True).click()
        pending.value.save_as(str(out/'checked.zip'))
        assert hashlib.sha256((out/'checked.zip').read_bytes()).hexdigest()==record['checked_archive_sha256']
        page.get_by_role('heading',name='Independent verification',exact=True).evaluate("el=>el.scrollIntoView({block:'start'})")
        page.screenshot(path=str(out/'01-checked-repair.png'))
        page.get_by_role('button',name='Recheck exported project without NVIDIA',exact=True).click()
        expect(page.get_by_text('Exported ZIP passed a fresh independent recheck. Zero model requests.',exact=True)).to_be_visible(timeout=120000)
        page.get_by_role('button',name='Find hidden failures without NVIDIA',exact=True).click()
        expect(page.get_by_text('No checked export: INDEPENDENT_FAILURE_FOUND',exact=True)).to_be_visible(timeout=60000)
        expect(page.get_by_role('button',name='Download property-checked project',exact=True)).to_have_count(0)
        page.get_by_role('heading',name='Independent verification',exact=True).evaluate("el=>el.scrollIntoView({block:'start'})")
        page.screenshot(path=str(out/'02-smoke-pass-independent-failure.png'))
        page.get_by_role('button',name='Show saved repair and evidence',exact=True).click()
        expect(page.get_by_role('button',name='Download property-checked project',exact=True)).to_be_visible()
        page.get_by_text('Independent FIFO contract · fixed before the run',exact=True).click()
        field=page.get_by_role('textbox',name='Contract JSON',exact=True)
        c=json.loads(field.input_value());c['data_width']=8;field.fill(json.dumps(c,indent=2));field.press('Tab')
        expect(page.get_by_role('button',name='Download property-checked project',exact=True)).to_have_count(0)
        page.get_by_role('button',name='Find hidden failures without NVIDIA',exact=True).click()
        expect(page.get_by_text('No checked export: PROPERTY_SETUP_REQUIRED',exact=True)).to_be_visible(timeout=60000)
        page.screenshot(path=str(out/'03-contract-change-hides-stale-success.png'))
        b.close()
    assert not errors and ledger==(ROOT/'.state/spend.json').read_bytes()
    report={'status':'PASS','browser_errors':errors,'new_model_calls':0,'download_matches_checked_hash':True,
            'export_reimport_fresh_recheck_passed':True,'smoke_pass_counterexample_visible':True,
            'failed_source_has_no_checked_export':True,'contract_change_hides_previous_success':True,'mismatched_width_rejected':True}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
