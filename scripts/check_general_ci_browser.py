"""Verify the actual web download and stale-result/tampered-audit rejection."""
import argparse
import io
import json
from pathlib import Path
import shutil
import zipfile

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent.parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url', default='http://127.0.0.1:8553')
    p.add_argument('--output', default='.tools/general-ci-browser')
    a = p.parse_args()
    out = (ROOT / a.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    ledger = (ROOT / '.state/spend.json').read_bytes()
    errors = []
    with sync_playwright() as w:
        browser = w.chromium.launch(executable_path=shutil.which('google-chrome'), headless=True, args=['--disable-dev-shm-usage', '--disable-gpu'])
        page = browser.new_page(viewport={'width': 1600, 'height': 1080}, accept_downloads=True)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(a.url + '/project', wait_until='domcontentloaded')
        page.locator('input[type=file]').set_input_files(str(ROOT / 'demo/general_project_ci/axis-register/checked-project.zip'))
        page.get_by_role('button', name='Check this project', exact=True).click()
        expect(page.get_by_text('The exact exported CI runner also passed. No model request.', exact=True)).to_be_visible(timeout=60000)
        page.get_by_text('The exact exported CI runner also passed. No model request.', exact=True).scroll_into_view_if_needed()
        page.screenshot(path=str(out / '01-standalone-export-gate.png'))
        with page.expect_download() as pending:
            page.get_by_role('button', name='Download checked project ZIP', exact=True).click()
        pending.value.save_as(str(out / 'checked-project.zip'))
        with zipfile.ZipFile(out / 'checked-project.zip') as z:
            assert {'rtlrefine_ci/run.py', 'rtlrefine_ci/engine.zip', 'rtlrefine_ci/manifest.json', '.github/workflows/rtlrefine.yml'} <= set(z.namelist())
            files = {n: z.read(n) for n in z.namelist()}
        config = json.loads(files['rtlrefine.json'])
        audit = next(t for t in config['tests'] if t['phase'] == 'audit')['files'][0]
        files[audit] += b'\n// unexpected audit change\n'
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for name, data in files.items():
                z.writestr(name, data)
        page.locator('input[type=file]').set_input_files({'name': 'changed-audit.zip', 'mimeType': 'application/zip', 'buffer': buffer.getvalue()})
        expect(page.get_by_role('button', name='Download checked project ZIP', exact=True)).to_have_count(0)
        page.get_by_role('button', name='Check this project', exact=True).click()
        expect(page.get_by_text('Protected CI input changed: ' + audit, exact=True)).to_be_visible(timeout=30000)
        page.screenshot(path=str(out / '02-changed-audit-rejected.png'))
        browser.close()
    assert not errors and ledger == (ROOT / '.state/spend.json').read_bytes()
    report = {'status': 'PASS', 'browser_errors': errors, 'new_model_calls': 0, 'actual_checked_zip_downloaded': True,
              'standalone_export_gate_passed': True, 'stale_download_hidden': True, 'changed_audit_rejected': True}
    (out / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
