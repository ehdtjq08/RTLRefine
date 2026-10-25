"""Exercise real ZIP upload, configured and unconfigured projects, and exports."""
import json
from pathlib import Path
import shutil
import zipfile
import io
import argparse

from playwright.sync_api import expect,sync_playwright

ROOT=Path(__file__).resolve().parent.parent


def pack(files,path):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items():archive.writestr(name,data)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8505');parser.add_argument('--output',default='.tools/project-browser-qa');args=parser.parse_args()
    out=ROOT/args.output;out.mkdir(exist_ok=False)
    import sys
    sys.path.insert(0,str(ROOT))
    from rtl_agent.project_repair.examples import example_files
    files=example_files()
    positive={k.replace('customer_top','nebula_design').replace('word_math','nebula_math'):
        v.replace(b'customer_top',b'nebula_design').replace(b'word_math',b'nebula_math').replace(b'129',b'257').replace(b'128',b'256').replace(b'lhs - rhs',b'lhs + rhs') for k,v in files.items()}
    positive['LICENSE']=b'MIT user-project test notice\n';pack(positive,out/'new-design.zip')
    without={k:v for k,v in files.items() if k!='rtlrefine.json'};pack(without,out/'unconfigured.zip')
    ledger=(ROOT/'.state/spend.json').read_bytes();errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu','--renderer-process-limit=1'])
        page=browser.new_page(viewport={'width':1440,'height':1080},accept_downloads=True);page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(args.url+'/project',wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='Bring your RTL. Bring your checks.',exact=True)).to_be_visible(timeout=30000)
        page.locator('input[type=file]').set_input_files(str(out/'new-design.zip'))
        expect(page.get_by_text('DUT: nebula_design',exact=False)).to_be_visible()
        expect(page.get_by_role('button',name='Repair this project with NVIDIA',exact=True)).to_be_disabled()
        page.get_by_role('button',name='Check this project',exact=True).click()
        expect(page.get_by_text('The exact project source passed every provided testbench.',exact=True)).to_be_visible(timeout=60000)
        expect(page.get_by_test_id('stMetric').filter(has_text='Provided testbenches').get_by_test_id('stMetricValue')).to_have_text('2/2')
        with page.expect_download() as pending:page.get_by_role('button',name='Download checked project ZIP',exact=True).click()
        pending.value.save_as(str(out/'checked-project.zip'))
        with zipfile.ZipFile(out/'checked-project.zip') as archive:
            for name,data in positive.items():
                if name!='rtlrefine.json':assert archive.read(name)==data
            assert b'nebula_design' in archive.read('rtlrefine.json')
        page.get_by_role('heading',name='Project verification',exact=True).scroll_into_view_if_needed();page.screenshot(path=str(out/'01_verified_257bit_project.png'))
        with page.expect_download() as pending:page.get_by_role('button',name='Download project evidence',exact=True).click()
        pending.value.save_as(str(out/'evidence.zip'))
        with zipfile.ZipFile(out/'evidence.zip') as archive:
            result=json.loads(archive.read('result.json'));assert result['accepted'] and result['api_requests']==0
            assert all(p['width']==257 for p in result['final_check']['tests'][0]['interface'][0]['ports'])
        page.locator('input[type=file]').set_input_files(str(out/'unconfigured.zip'))
        expect(page.get_by_role('button',name='Download checked project ZIP',exact=True)).to_have_count(0)
        expect(page.get_by_text('Project name',exact=True)).to_be_visible()
        expect(page.get_by_test_id('stSelectbox').filter(has_text='DUT top module')).to_be_visible()
        page.get_by_role('button',name='Check this project',exact=True).click()
        expect(page.get_by_text('This source was not accepted: PUBLIC_TESTS_FAILED',exact=True)).to_be_visible(timeout=60000)
        expect(page.get_by_role('button',name='Download checked project ZIP',exact=True)).to_have_count(0)
        page.screenshot(path=str(out/'02_wizard_and_failure.png'));browser.close()
    assert not errors and ledger==(ROOT/'.state/spend.json').read_bytes()
    report={'status':'PASS','new_model_calls':0,'browser_errors':errors,'new_top_and_257bit_ports':True,
        'multifile_functions_verified':True,'downloaded_project_matches_input_files':True,'license_asset_preserved':True,
        'missing_manifest_wizard_works':True,'stale_acceptance_hidden_on_upload_change':True,'failed_project_not_exported_as_checked':True}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
