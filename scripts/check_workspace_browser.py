"""Actual designer upload/edit/verification/export flow; no model calls."""
import hashlib
import argparse
import json
import re
import shutil
import zipfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".tools/workspace-browser-qa-v2")
    args = parser.parse_args()
    output = ROOT / args.output
    output.mkdir(exist_ok=False)
    before = (ROOT / ".state/spend.json").read_bytes()
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which("google-chrome"), headless=True, args=["--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 1440, "height": 1100}, accept_downloads=True)
        page.on("pageerror", lambda error: errors.append(str(error)))
        def run_check(status):
            ids = page.get_by_text(re.compile(r"^Review ID: ")).all_text_contents()
            previous = ids[0] if ids else None
            page.get_by_role("button", name="Run independent checks", exact=True).click()
            current = page.get_by_text(re.compile(r"^Review ID: "))
            if previous:
                expect(current).not_to_have_text(previous, timeout=60000)
            expect(current).to_be_visible(timeout=60000)
            expect(page.get_by_text(status, exact=True)).to_be_visible(timeout=60000)
            page.wait_for_timeout(300)
        page.goto("http://127.0.0.1:8502", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="An AI fix needs evidence.", exact=True)).to_be_visible(timeout=30000)
        page.get_by_role("link", name="Open the editable RTL workspace", exact=True).click()
        expect(page.get_by_role("heading", name="Check your RTL change.", exact=True)).to_be_visible(timeout=30000)
        run_check("NOT ACCEPTED · SIMULATION_FAILED")
        page.get_by_role("heading", name="Independent review result", exact=True).scroll_into_view_if_needed()
        page.screenshot(path=str(output / "01_original_failure.png"))
        page.get_by_text("Recorded NVIDIA candidate", exact=True).click()
        expect(page.get_by_text("The source changed.", exact=False)).to_be_visible()
        run_check("VERIFIED WITHIN BOUND · Every directed regression and bounded comparison passed.")
        current = json.loads((ROOT / "demo/fifo_reset/current.json").read_text())
        selected = (ROOT / "demo/fifo_reset" / current["accepted_rtl"]).read_text()
        edited = selected + "\n// Designer review: same logic, independently checked uploaded bytes.\n"
        page.get_by_role("textbox", name="RTL source", exact=True).fill(edited)
        page.get_by_role("textbox", name="RTL source", exact=True).press("Tab")
        expect(page.get_by_text("The source changed.", exact=False)).to_be_visible()
        run_check("VERIFIED WITHIN BOUND · Every directed regression and bounded comparison passed.")
        expect(page.get_by_text("Reviewed source SHA-256: " + hashlib.sha256(edited.encode()).hexdigest(), exact=True)).to_be_visible(timeout=60000)
        with page.expect_download() as item:
            page.get_by_role("button", name="Download verified RTL", exact=True).click()
        item.value.save_as(str(output / "edited_fifo.v"))
        assert (output / "edited_fifo.v").read_text() == edited
        selector = page.get_by_test_id("stSelectbox").get_by_role("combobox")
        selector.click()
        page.get_by_role("option", name="Frame FIFO backpressure", exact=True).click()
        page.get_by_text("My RTL", exact=True).click()
        expect(page.get_by_text("Source selection: Frame FIFO backpressure · My RTL · template", exact=True)).to_be_visible(timeout=30000)
        page.locator('input[type="file"]').set_input_files(str(ROOT / "third_party/verilog_axis_frame/axis_fifo.v"))
        expect(page.get_by_text("Uploaded source: axis_fifo.v", exact=True)).to_be_visible(timeout=30000)
        run_check("NOT ACCEPTED · SIMULATION_FAILED")
        page.locator('input[type="file"]').set_input_files(str(ROOT / "third_party/verilog_axis_frame/fixed_axis_fifo.v"))
        expect(page.get_by_text("Uploaded source: fixed_axis_fifo.v", exact=True)).to_be_visible(timeout=30000)
        run_check("VERIFIED WITHIN BOUND · Every directed regression and bounded comparison passed.")
        expect(page.get_by_text("Reviewed source SHA-256: " + hashlib.sha256((ROOT / "third_party/verilog_axis_frame/fixed_axis_fifo.v").read_bytes()).hexdigest(), exact=True)).to_be_visible(timeout=60000)
        page.get_by_role("heading", name="Independent review result", exact=True).scroll_into_view_if_needed()
        page.screenshot(path=str(output / "02_uploaded_frame_fix.png"))
        with page.expect_download() as item:
            page.get_by_role("button", name="Download this review's evidence", exact=True).click()
        item.value.save_as(str(output / "frame_review.zip"))
        with zipfile.ZipFile(output / "frame_review.zip") as archive:
            manifest = json.loads(archive.read("manifest.json"))
            assert len(archive.namelist()) == len(manifest) + 1
            for name, entry in manifest.items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == entry["sha256"]
            assert archive.read("candidate.v") == (ROOT / "third_party/verilog_axis_frame/fixed_axis_fifo.v").read_bytes()
            assert archive.read("COPYING") == (ROOT / "third_party/verilog_axis_frame/COPYING").read_bytes()
            report = json.loads(archive.read("review.json"))
            assert report["accepted"] and report["new_api_calls"] == 0
            assert len(report["simulations"]) == 3 and report["bounded_comparisons"][0]["steps"] == 12
            assert not any(name.endswith(".vvp") or ".env" in name for name in archive.namelist())
        page.get_by_text("Ask NVIDIA to repair the failing change", exact=True).click()
        expect(page.get_by_role("button", name="Ask NVIDIA to repair this failing change", exact=True)).to_be_disabled()
        browser.close()
    assert not errors
    assert before == (ROOT / ".state/spend.json").read_bytes()
    result = {"status": "PASS", "new_model_calls": 0, "browser_errors": errors,
              "original_failure_reproduced": True, "edited_nvidia_candidate_verified": True,
              "stale_result_labeled_after_edit": True, "uploaded_frame_bug_rejected": True,
              "uploaded_maintainer_control_verified": True, "download_matches_exact_checked_bytes": True,
              "evidence_license_and_hashes_verified": True}
    (output / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
