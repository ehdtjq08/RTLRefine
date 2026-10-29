"""Check external provenance, exact downloads and genuine no-inference rechecks."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parent.parent


def main():
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8551');p.add_argument('--output',default='.tools/external-validation-browser');a=p.parse_args()
    out=ROOT/a.output;out.mkdir(exist_ok=False);ledger=(ROOT/'.state/spend.json').read_bytes();errors=[]
    with sync_playwright() as w:
        b=w.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu'])
        page=b.new_page(viewport={'width':1600,'height':1000},accept_downloads=True);page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(a.url+'/external-validation',wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='Validated on independently developed RTL.',exact=True)).to_be_visible(timeout=30000)
        page.get_by_role('tab',name='Known upstream regression repair',exact=True).click()
        expect(page.get_by_text('The exact NVIDIA-selected source passed all eight benches and a fresh export reimport.',exact=True)).to_be_visible()
        axis=page.get_by_role('tabpanel',name='Known upstream regression repair',exact=True)
        axis.get_by_test_id('stCode').evaluate("e=>e.scrollIntoView({block:'start'})");page.screenshot(path=str(out/'01-real-upstream-repair.png'))
        with page.expect_download() as pending:page.get_by_role('button',name='Download externally checked NVIDIA repair',exact=True).click()
        pending.value.save_as(str(out/'checked.zip'))
        expected=(ROOT/'demo/external_rtl_validation/projects/axis-register-nvidia-repaired.zip').read_bytes()
        assert hashlib.sha256((out/'checked.zip').read_bytes()).hexdigest()==hashlib.sha256(expected).hexdigest()
        page.get_by_role('button',name='Recheck external NVIDIA repair without inference',exact=True).click()
        expect(page.get_by_text('Fresh external project recheck passed. Zero model requests.',exact=True)).to_be_visible(timeout=60000)
        page.get_by_role('button',name='Reproduce upstream regression without inference',exact=True).click()
        expect(page.get_by_text('Known upstream capacity/throughput regression reproduced. No checked export. Zero model requests.',exact=True)).to_be_visible(timeout=30000)
        page.screenshot(path=str(out/'02-genuine-regression-reproduced.png'))
        page.get_by_role('tab',name='Second-author healthy control',exact=True).click()
        expect(page.get_by_role('heading',name='ZipCPU · skid buffer',exact=True)).to_be_visible()
        page.get_by_role('button',name='Recheck ZipCPU healthy control without inference',exact=True).click()
        expect(page.get_by_role('tabpanel',name='Second-author healthy control',exact=True).get_by_text('Fresh external project recheck passed. Zero model requests.',exact=True)).to_be_visible(timeout=60000)
        page.screenshot(path=str(out/'03-second-author-control.png'));b.close()
    assert not errors and ledger==(ROOT/'.state/spend.json').read_bytes()
    report={'status':'PASS','browser_errors':errors,'new_model_calls':0,'exact_checked_zip_download':True,
            'selected_external_recheck_passed':True,'genuine_upstream_regression_reproduced':True,'second_author_healthy_recheck_passed':True}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
