"""Check captured UART samples, exact download and no-inference replays."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent


def main():
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8556');p.add_argument('--output',default='.tools/uart-peer-browser');a=p.parse_args()
    out=(ROOT/a.output).resolve();out.mkdir(parents=True,exist_ok=False)
    ledger=(ROOT/'.state/spend.json').read_bytes();errors=[]
    with sync_playwright() as w:
        browser=w.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--disable-dev-shm-usage','--disable-gpu'])
        page=browser.new_page(viewport={'width':1600,'height':1100},accept_downloads=True);page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(a.url+'/external-validation',wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='UART · loopback and independent serial peers',exact=True)).to_be_visible(timeout=30000)
        table=page.locator('table').filter(has=page.get_by_text('Original transmitter',exact=True))
        expect(table.get_by_role('row').filter(has_text='Original transmitter')).to_contain_text('0x80')
        expect(table.get_by_role('row').filter(has_text='NVIDIA-selected transmitter')).to_contain_text('0x01')
        page.screenshot(path=str(out/'01-loopback-and-peer-bits.png'))
        page.get_by_role('combobox',name='Inspect a captured public word').click()
        page.get_by_role('option',name='0x96',exact=True).click()
        expect(table.get_by_role('row').filter(has_text='Original transmitter')).to_contain_text('0x69')
        expect(table.get_by_role('row').filter(has_text='NVIDIA-selected transmitter')).to_contain_text('0x96')
        with page.expect_download() as pending:page.get_by_role('button',name='Download checked UART pair with CI',exact=True).click()
        pending.value.save_as(str(out/'uart-checked.zip'))
        expected=(ROOT/'demo/uart_peer/projects/uart-nvidia-checked-ci.zip').read_bytes()
        assert hashlib.sha256((out/'uart-checked.zip').read_bytes()).hexdigest()==hashlib.sha256(expected).hexdigest()
        page.get_by_role('button',name='Recheck UART repair and CI without inference',exact=True).click()
        expect(page.get_by_text('Fresh UART peer and exported CI checks passed. Zero model requests.',exact=True)).to_be_visible(timeout=60000)
        page.get_by_role('button',name='Reproduce original UART peer mismatch without inference',exact=True).click()
        expect(page.get_by_text('Original UART peer mismatch reproduced. No checked export. Zero model requests.',exact=True)).to_be_visible(timeout=30000)
        page.get_by_role('button',name='Run original loopback-only smoke without inference',exact=True).click()
        expect(page.get_by_text('Loopback-only smoke passed. This does not check the independent LSB-first peer contract. Zero model requests.',exact=True)).to_be_visible(timeout=30000)
        page.get_by_role('button',name='Run exported UART regression cycle without inference',exact=True).click()
        expect(page.get_by_text('Exported UART CI reproduced 0 → 1 → 0. Zero model requests.',exact=True)).to_be_visible(timeout=60000)
        page.screenshot(path=str(out/'02-native-replays.png'))
        assert page.get_by_test_id('stException').count()==0
        browser.close()
    assert not errors and ledger==(ROOT/'.state/spend.json').read_bytes()
    report={'status':'PASS','browser_errors':errors,'captured_bits_match_actual_records':True,'word_selection_updates_actual_samples':True,
            'exact_checked_zip_downloaded':True,'repair_and_standalone_ci_rechecked':True,'original_peer_failure_reproduced':True,
            'limited_loopback_smoke_pass_reproduced':True,'exported_ci_cycle':[0,1,0],'new_model_calls':0}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
