"""Verify the designer edit path and actionable compiler failures, with no API."""
import argparse
import json
from pathlib import Path
import shutil

from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parent.parent


def main():
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8543');p.add_argument('--output',default='.tools/editor-browser-final');a=p.parse_args()
    out=ROOT/a.output;out.mkdir(exist_ok=False);errors=[];ledger=(ROOT/'.state/spend.json').read_bytes()
    with sync_playwright() as w:
        b=w.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu'])
        page=b.new_page(viewport={'width':1600,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(a.url+'/properties',wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='A passing test can still miss a bug.',exact=True)).to_be_visible(timeout=30000)
        page.get_by_text('Original design source',exact=True).click()
        page.get_by_text('Edit permitted DUT logic before checking',exact=True).click()
        field=page.get_by_role('textbox',name='DUT source',exact=True);old=field.input_value()
        fixed=old.replace("2'b11: count <= count + 1;","2'b11: count <= count;");assert old!=fixed
        field.fill(fixed);field.press('Tab')
        expect(page.get_by_role('button',name='Download property-checked project',exact=True)).to_have_count(0)
        page.get_by_role('button',name='Find hidden failures without NVIDIA',exact=True).click()
        expect(page.get_by_text('The exact project passed tests, bounded properties and progress checks.',exact=True)).to_be_visible(timeout=120000)
        page.get_by_role('heading',name='Independent verification',exact=True).evaluate("e=>e.scrollIntoView({block:'start'})")
        page.screenshot(path=str(out/'01-designer-fix-checked.png'))
        field.fill(fixed+'\n// source changed after verification\n');field.press('Tab')
        expect(page.get_by_role('button',name='Download property-checked project',exact=True)).to_have_count(0)
        field.fill(fixed+'\nendmodule\n');field.press('Tab')
        page.get_by_role('button',name='Find hidden failures without NVIDIA',exact=True).click()
        expect(page.get_by_text('No checked export: PUBLIC_TEST_SETUP_REQUIRED',exact=True)).to_be_visible(timeout=30000)
        expect(page.get_by_text('Original compilation or setup diagnostics',exact=True)).to_be_visible()
        expect(page.get_by_test_id('stCode').filter(has_text='syntax error')).to_be_visible()
        page.get_by_role('heading',name='Independent verification',exact=True).evaluate("e=>e.scrollIntoView({block:'start'})")
        page.screenshot(path=str(out/'02-compiler-diagnostic.png'));b.close()
    assert not errors and ledger==(ROOT/'.state/spend.json').read_bytes()
    result={'status':'PASS','new_model_calls':0,'designer_edits_receive_full_checks':True,
            'changed_source_hides_old_export':True,'syntax_error_shown_inline':True,'browser_errors':errors}
    (out/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
