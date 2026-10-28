"""Exercise JSON-free setup and the complete export/regression/reimport flow."""
import argparse
import io
import json
from pathlib import Path
import re
import shutil
import sys
import zipfile

from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from rtl_agent.property_repair.examples import example_files


def pack(files,path):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)


def main():
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8541');p.add_argument('--output',default='.tools/functional-browser-final');args=p.parse_args()
    out=ROOT/args.output;out.mkdir(exist_ok=False);errors=[];ledger=(ROOT/'.state/spend.json').read_bytes()
    files=example_files('healthy');files={k:v for k,v in files.items() if not k.endswith('.json')}
    mapping={'packet_queue':'customer_queue','clk':'clock_in','rst':'reset','s_valid':'in_valid','s_ready':'in_ready','s_data':'payload',
             'm_valid':'out_valid','m_ready':'out_ready','m_data':'word'}
    pattern=re.compile(r'\b('+('|'.join(mapping))+r')\b')
    files={k:pattern.sub(lambda m:mapping[m.group()],v.decode()).encode() for k,v in files.items()}
    files['rtl/customer_queue.sv']=files.pop('rtl/packet_queue.sv');files['LICENSE']=(ROOT/'LICENSE').read_bytes()
    pack(files,out/'without-json.zip')
    with sync_playwright() as w:
        b=w.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu'])
        page=b.new_page(viewport={'width':1600,'height':1000},accept_downloads=True);page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(args.url+'/properties',wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='A passing test can still miss a bug.',exact=True)).to_be_visible(timeout=30000)
        page.locator('input[type=file]').set_input_files(str(out/'without-json.zip'))
        expect(page.get_by_text('Project name',exact=True)).to_be_visible()
        page.get_by_role('button',name='Inspect FIFO ports without NVIDIA',exact=True).click()
        expect(page.get_by_test_id('stSelectbox').filter(has_text='Contract port: clk')).to_be_visible(timeout=30000)
        expect(page.get_by_role('button',name='Repair from a counterexample with NVIDIA',exact=True)).to_be_disabled()
        page.screenshot(path=str(out/'01-no-json-setup.png'))
        page.get_by_role('button',name='Find hidden failures without NVIDIA',exact=True).click()
        expect(page.get_by_text('The exact project passed tests, bounded properties and progress checks.',exact=True)).to_be_visible(timeout=120000)
        page.get_by_role('button',name='Run standalone regressions without NVIDIA',exact=True).click()
        expect(page.get_by_text('Standalone regressions passed · exit 0 · 1/1 cases. Zero model calls.',exact=True)).to_be_visible(timeout=30000)
        with page.expect_download() as pending:page.get_by_role('button',name='Download property-checked project',exact=True).click()
        pending.value.save_as(str(out/'checked.zip'))
        with zipfile.ZipFile(out/'checked.zip') as z:
            for name,data in files.items():assert z.read(name)==data,name
            config=json.loads(z.read('rtlrefine.json'));contract=json.loads(z.read('fifo_contract.json'))
            assert config['dut_top']=='customer_queue' and contract['ports']['clk']=='clock_in'
            assert 'rtlrefine_regressions/run.py' in z.namelist()
            mutated={name:z.read(name) for name in z.namelist()}
        page.get_by_role('heading',name='Independent verification',exact=True).evaluate("e=>e.scrollIntoView({block:'start'})")
        page.screenshot(path=str(out/'02-export-includes-regressions.png'))
        old=mutated['rtl/customer_queue.sv'];new=old.replace(b"2'b11: count <= count;",b"2'b11: count <= count + 1;")
        assert new!=old;mutated['rtl/customer_queue.sv']=new;pack(mutated,out/'reintroduced-bug.zip')
        page.locator('input[type=file]').set_input_files(str(out/'reintroduced-bug.zip'))
        expect(page.get_by_role('button',name='Download property-checked project',exact=True)).to_have_count(0)
        page.get_by_role('button',name='Find hidden failures without NVIDIA',exact=True).click()
        expect(page.get_by_text('No checked export: INDEPENDENT_FAILURE_FOUND',exact=True)).to_be_visible(timeout=60000)
        page.get_by_role('button',name='Run original failing regressions',exact=True).click()
        expect(page.get_by_text(re.compile(r'^Original bug reproduced · exit 1 ·'))).to_be_visible(timeout=30000)
        with page.expect_download() as pending:page.get_by_role('button',name='Download failing reproduction and tests',exact=True).click()
        pending.value.save_as(str(out/'failing-reproduction.zip'))
        page.get_by_role('heading',name='Independent verification',exact=True).evaluate("e=>e.scrollIntoView({block:'start'})")
        page.screenshot(path=str(out/'03-reintroduced-bug-caught.png'))
        page.goto(args.url+'/project',wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='Bring your RTL. Bring your checks.',exact=True)).to_be_visible(timeout=30000)
        page.locator('input[type=file]').set_input_files(str(out/'reintroduced-bug.zip'))
        expect(page.get_by_text('This export retains its FIFO contract and regression suite.',exact=False)).to_be_visible()
        page.get_by_role('button',name='Check this project',exact=True).click()
        expect(page.get_by_text('No checked export: INDEPENDENT_FAILURE_FOUND',exact=True)).to_be_visible(timeout=60000)
        expect(page.get_by_role('button',name='Download property-checked project',exact=True)).to_have_count(0)
        page.screenshot(path=str(out/'04-general-route-retains-checks.png'));b.close()
    assert not errors and ledger==(ROOT/'.state/spend.json').read_bytes()
    result={'status':'PASS','browser_errors':errors,'new_model_calls':0,'no_json_setup_works':True,
            'custom_top_ports_and_filename':True,'original_assets_and_license_preserved':True,
            'checked_export_contains_portable_suite':True,'actual_standalone_python_run_exit_zero':True,
            'reintroduced_bug_rejected':True,'failing_reproduction_script_exits_one':True,'stale_export_hidden':True,
            'generic_project_route_cannot_skip_fifo_checks':True}
    (out/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
