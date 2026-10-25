"""Browser verification of the actual external UART case and zero-API rechecks."""
import hashlib
import argparse
import json
from pathlib import Path
import shutil
import zipfile

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".tools/external-uart-browser-qa-v5")
    args = parser.parse_args()
    output = ROOT / args.output
    output.mkdir(exist_ok=False)
    before = (ROOT / ".state/spend.json").read_bytes()
    summary = json.loads((ROOT / "demo/external_uart/run/summary.json").read_text())
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which("google-chrome"), headless=True,
                                     args=["--disable-dev-shm-usage", "--disable-gpu", "--renderer-process-limit=1"])
        page = browser.new_page(viewport={"width": 1440, "height": 1100}, accept_downloads=True)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:8502/uart", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="The receiver said stop. The UART sent anyway.", exact=True)).to_be_visible(timeout=30000)
        expect(page.get_by_test_id("stMetric").filter(has_text="Actual NVIDIA requests").get_by_test_id("stMetricValue")).to_have_text(str(summary["unique_paid_calls"]))
        expect(page.get_by_role("heading", name="Original: a legal writer trusts a false ready indication", exact=True)).to_be_visible()
        expect(page.get_by_text("Request 1: SIMULATION_FAILED", exact=True)).to_be_visible()
        page.screenshot(path=str(output / "01_real_uart_failure.png"))
        page.get_by_text("Edit and check UART", exact=True).click()
        panel = page.get_by_test_id("stMain")
        if summary["accepted"]:
            panel.get_by_text("Recorded NVIDIA candidate", exact=True).click()
        panel.get_by_role("button", name="Run UART specification checks", exact=True).click()
        if summary["accepted"]:
            expect(panel.get_by_text("VERIFIED AGAINST SPEC WITHIN BOUND", exact=True)).to_be_visible(timeout=60000)
            expected = (ROOT / "demo/external_uart/run" / summary["accepted_source"]).read_bytes()
            with page.expect_download() as download:
                panel.get_by_role("button", name="Download checked UART RTL", exact=True).click()
            download.value.save_as(str(output / "txuart.v"))
            assert (output / "txuart.v").read_bytes() == expected
        else:
            expect(panel.get_by_text("NOT ACCEPTED · SIMULATION_FAILED", exact=True)).to_be_visible(timeout=60000)
            expected = (ROOT / "demo/external_uart/run/input.v").read_bytes()
        expect(panel.get_by_test_id("stMetric").filter(has_text="Golden RTL used for scoring").get_by_test_id("stMetricValue")).to_have_text("No")
        expect(panel.get_by_text("Checked RTL SHA-256: " + hashlib.sha256(expected).hexdigest(), exact=True)).to_be_visible()
        page.screenshot(path=str(output / "02_fresh_uart_check.png"))
        with page.expect_download() as download:
            panel.get_by_role("button", name="Download UART evidence", exact=True).click()
        download.value.save_as(str(output / "evidence.zip"))
        with zipfile.ZipFile(output / "evidence.zip") as archive:
            manifest = json.loads(archive.read("manifest.json"))
            assert len(archive.namelist()) == len(manifest) + 1
            for name, record in manifest.items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == record["sha256"]
            assert archive.read("candidate.v") == expected
            assert "LICENSE" in manifest and "public_contract/contract.json" in manifest and "formal_0/properties.v" in manifest
            assert "checker_source/rtl_agent__uart_external__simulation.py" in manifest
            assert not any("maintainer_fixed" in name or name.endswith(".vvp") or ".env" in name for name in manifest)
        # Editing invalidates a previous pass immediately.
        panel.get_by_role("textbox", name="Editable UART RTL", exact=True).fill("module changed; endmodule")
        panel.get_by_role("textbox", name="Editable UART RTL", exact=True).press("Tab")
        expect(panel.get_by_text("Source changed. Check the current source before using a previous result.", exact=True)).to_be_visible(timeout=15000)
        expect(panel.get_by_role("button", name="Download checked UART RTL", exact=True)).to_have_count(0)
        browser.close()
    assert not errors
    assert before == (ROOT / ".state/spend.json").read_bytes()
    result = {"status": "PASS", "new_model_calls": 0, "browser_errors": errors, "historical_external_scope_visible": True,
              "initial_wrong_keep_visible": True, "fresh_spec_check_accepted": summary["accepted"], "exact_rtl_and_evidence_hashes_verified": True,
              "golden_reference_used": False, "gpl_license_in_evidence": True, "stale_source_result_invalidated": True}
    (output / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
