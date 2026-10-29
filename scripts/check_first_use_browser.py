"""Audit an existing fixture through the real no-manifest UI and exported CI.

This is automated workflow testing, not an external designer/user study. It
reuses existing importer regression fixtures and creates no new repair sample.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
RENAME={'rtl/customer_top.sv':'src/customer_top.sv','rtl/word_math.sv':'src/word_math.sv',
        'tests/public.sv':'sim/public_tb.sv','tests/audit.sv':'sim/stress_tb.sv','LICENSE':'LICENSE'}


def packed(files):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(files.items()):z.writestr(name,data)
    return stream.getvalue()


def fixture(literal=False):
    with zipfile.ZipFile(ROOT/'submission/hackathon-2026/examples/wide-math-fixed.zip') as z:
        files={new:z.read(old) for old,new in RENAME.items()}
    if literal:
        # Exactly the completion variant already exercised by
        # tests/test_project_repair.py; assertions/design logic are unchanged.
        for path in ('sim/public_tb.sv','sim/stress_tb.sv'):
            files[path]=files[path].replace(b'`include "rtlrefine_check.vh"',b'').replace(
                b'`RTLREFINE_DONE(checks);',b'$display("ALL_TESTS_PASSED"); $finish;')
    return files


def execute_export(project,out):
    out.mkdir()
    report=out/'report.json';junit=out/'junit.xml'
    process=subprocess.run([sys.executable,'-I',str(project/'rtlrefine_ci/run.py'),'--report',str(report),'--junit',str(junit)],
        cwd=project,env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'HOME':'/nonexistent','LANG':'C'},capture_output=True,text=True,timeout=195)
    (out/'stdout.json').write_text(process.stdout);(out/'stderr.log').write_text(process.stderr)
    result=json.loads(report.read_text());assert result['new_model_calls']==0 and junit.exists()
    return {'exit_code':process.returncode,'status':result['status'],'accepted':result['accepted'],
            'testbenches':len(result.get('tests',[])),'junit_report':True,'new_model_calls':0}


def main():
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8561');p.add_argument('--output',default='.tools/first-use-final');p.add_argument('--fault-flag');a=p.parse_args()
    out=(ROOT/a.output).resolve();out.mkdir(parents=True,exist_ok=False)
    flag=Path(a.fault_flag).resolve() if a.fault_flag else None
    if flag:flag.unlink(missing_ok=True)
    ledger_path=ROOT/'.state/spend.json'
    ledger=ledger_path.read_bytes() if ledger_path.exists() else None
    errors=[];scenarios=[];started=time.monotonic()
    with sync_playwright() as w:
        browser=w.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu'])
        for kind in ('unchanged_macro_benches','existing_literal_variant'):
            folder=out/kind;folder.mkdir();files=fixture(literal=kind=='existing_literal_variant')
            blob=packed(files);(folder/'input.zip').write_bytes(blob)
            page=browser.new_page(viewport={'width':1550,'height':1050},accept_downloads=True);page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(a.url+'/',wait_until='domcontentloaded');page.get_by_text('Open your own RTL project',exact=True).click()
            expect(page.get_by_role('heading',name='Bring your RTL. Bring your checks.',exact=True)).to_be_visible(timeout=30000)
            page.locator('input[type=file]').set_input_files({'name':kind+'.zip','mimeType':'application/zip','buffer':blob})
            rtl=page.get_by_test_id('stMultiSelect').filter(has=page.get_by_text('RTL files (compile order)',exact=True))
            expect(rtl).to_contain_text('src/customer_top.sv');expect(rtl).to_contain_text('src/word_math.sv')
            expect(rtl).not_to_contain_text('sim/public_tb.sv');expect(rtl).not_to_contain_text('sim/stress_tb.sv')
            audit=page.get_by_test_id('stMultiSelect').filter(has=page.get_by_text('Additional testbenches withheld from the model (optional)',exact=True))
            audit.get_by_role('combobox').click();page.get_by_role('option',name='sim/stress_tb.sv',exact=True).click()
            if kind=='existing_literal_variant':
                expect(page.get_by_role('textbox',name='Success text printed only after all public checks pass',exact=True)).to_have_value('ALL_TESTS_PASSED')
                expect(page.get_by_role('textbox',name='Additional success text: sim/stress_tb.sv',exact=True)).to_have_value('ALL_TESTS_PASSED')
            expect(page.get_by_role('button',name='Repair this project with NVIDIA',exact=True)).to_be_disabled()
            page.get_by_role('button',name='Check this project',exact=True).click()
            success='The exact exported CI runner also passed. No model request.'
            expect(page.get_by_text(success,exact=True)).to_be_visible(timeout=60000)
            page.get_by_text(success,exact=True).scroll_into_view_if_needed();page.screenshot(path=str(folder/'configured-and-checked.png'))
            with page.expect_download() as pending:page.get_by_role('button',name='Download checked project ZIP',exact=True).click()
            checked=folder/'checked-project.zip';pending.value.save_as(str(checked))
            with page.expect_download() as pending:page.get_by_role('button',name='Download project evidence',exact=True).click()
            evidence=folder/'evidence.zip';pending.value.save_as(str(evidence))
            with zipfile.ZipFile(evidence) as z:
                recorded=json.loads(z.read('result.json'));assert recorded['accepted'] and recorded['api_requests']==0
                assert recorded['public_tests']==1 and recorded['audit_tests']==1
            with zipfile.ZipFile(checked) as z:exported={n:z.read(n) for n in z.namelist()}
            assert all(exported[n]==data for n,data in files.items()),'The export changed original HDL, assertions or license'
            assert {'rtlrefine_ci/run.py','rtlrefine_ci/engine.zip','.github/workflows/rtlrefine.yml'}<=set(exported)
            project=folder/'extracted';project.mkdir()
            for name,data in exported.items():
                target=project/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            source=project/'src/word_math.sv';good=source.read_bytes();bad=good.replace(b'lhs + rhs',b'lhs - rhs');assert bad!=good
            cycle=[]
            for phase,data in [('checked',good),('bug_reintroduced',bad),('restored',good)]:
                source.write_bytes(data);r=execute_export(project,folder/phase);r['phase']=phase;cycle.append(r)
            assert [r['exit_code'] for r in cycle]==[0,1,0]
            bad_files={**exported,'src/word_math.sv':bad}
            page.locator('input[type=file]').set_input_files({'name':'changed-design.zip','mimeType':'application/zip','buffer':packed(bad_files)})
            expect(page.get_by_role('button',name='Download checked project ZIP',exact=True)).to_have_count(0)
            page.get_by_role('button',name='Check this project',exact=True).click()
            expect(page.get_by_text('This source was not accepted: PUBLIC_TESTS_FAILED',exact=True)).to_be_visible(timeout=60000)
            expect(page.get_by_test_id('stCode').filter(has_text='SUM mismatch').first).to_be_visible()
            page.get_by_test_id('stCode').filter(has_text='SUM mismatch').first.scroll_into_view_if_needed();page.screenshot(path=str(folder/'failing-assertion-visible.png'))
            page.locator('input[type=file]').set_input_files(str(checked));page.get_by_role('button',name='Check this project',exact=True).click()
            expect(page.get_by_text(success,exact=True)).to_be_visible(timeout=60000)
            injected=False
            if flag:
                flag.touch()
                try:
                    page.get_by_role('button',name='Check this project',exact=True).click()
                    expect(page.get_by_text('Controlled first-use backend failure; no model call was made',exact=True)).to_be_visible(timeout=30000)
                    expect(page.get_by_role('button',name='Download checked project ZIP',exact=True)).to_have_count(0)
                    expect(page.get_by_text(success,exact=True)).to_have_count(0)
                    page.screenshot(path=str(folder/'fresh-failure-clears-old-success.png'));injected=True
                finally:flag.unlink(missing_ok=True)
            assert page.get_by_test_id('stException').count()==0
            scenarios.append({'input':kind,'entered_from_homepage':True,'no_manifest_or_json_edit':True,'rtl_and_test_roles_selected':True,
                'existing_completion_recognized':True,'public_and_audit_passed':True,'all_original_input_bytes_preserved':True,
                'exact_checked_zip_and_evidence_downloaded':True,'standalone_cycle':cycle,'changed_source_hides_old_download':True,
                'failing_assertion_visible_without_log_expansion':True,'checked_export_reimport_passed':True,
                'controlled_backend_error_clears_old_success':injected,'new_model_calls':0})
            page.close()
        browser.close()
    after=ledger_path.read_bytes() if ledger_path.exists() else None
    assert not errors and ledger==after
    report={'status':'PASS','automated_workflow_audit':True,'external_human_user_study':False,'new_repair_sample':False,
            'fixture_origin':'Existing public 129-bit importer fixture and its already-tested literal-completion variant; conventional file paths only.',
            'browser_errors':errors,'new_model_calls':0,'wall_seconds':time.monotonic()-started,'scenarios':scenarios}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
