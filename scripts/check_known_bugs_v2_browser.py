"""Real browser: paired metrics, a feedback-only repair and rejected overfitting."""
import hashlib
import argparse
import json
from pathlib import Path
import re
import shutil
import zipfile

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".tools/known-bugs-v2-browser-qa-final")
    output = ROOT / parser.parse_args().output
    output.mkdir(exist_ok=False)
    ledger = (ROOT / ".state/spend.json").read_bytes()
    summary = json.loads((ROOT / "demo/known_bug_comparison_v2/run/summary.json").read_text())
    successful = next(p for p in summary["pairs"] if p["kind"] == "historical_defect" and p["arms"]["checker_feedback"]["accepted"])
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which("google-chrome"), headless=True,
                                     args=["--disable-dev-shm-usage", "--disable-gpu", "--renderer-process-limit=1"])
        page = browser.new_page(viewport={"width": 1440, "height": 1100}, accept_downloads=True)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("http://127.0.0.1:8502/benchmarks", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="A fair test on known RTL bugs.", exact=True)).to_be_visible(timeout=30000)
        for label, text in (("Self-review trace passes", f"{summary['totals']['self_review']['real_trace_passes']}/9"), ("Execution-feedback trace passes", f"{summary['totals']['checker_feedback']['real_trace_passes']}/9"), ("Unique NVIDIA calls", str(summary['unique_paid_calls']))):
            expect(page.get_by_test_id("stMetric").filter(has_text=label).get_by_test_id("stMetricValue")).to_have_text(text)
        expect(page.get_by_text("Known historical research-artifact versions", exact=False)).to_be_visible()
        page.screenshot(path=str(output / "01_complete_comparison.png"))
        page.get_by_text("Inspect and check a candidate", exact=True).click()
        def select(identity):
            page.get_by_test_id("stSelectbox").get_by_role("combobox").click()
            page.get_by_role("option", name=re.compile("^" + identity + " · ")).click()
        select(successful["opaque_id"])
        page.get_by_text("checker_feedback", exact=True).click()
        expect(page.get_by_text("Recorded outcome: ALL_SEALED_TRACES_PASS", exact=True)).to_be_visible()
        page.get_by_text("Recorded model candidate", exact=True).click()
        page.get_by_role("button", name="Run sealed regression checks", exact=True).click()
        expect(page.get_by_role("button", name="Download current checked RTL", exact=True)).to_be_visible(timeout=90000)
        source_path = ROOT / "demo/known_bug_comparison_v2/run" / successful["opaque_id"] / successful["arms"]["checker_feedback"]["request_path"] / "candidate.v"
        expected = source_path.read_bytes()
        digest = hashlib.sha256(expected).hexdigest()
        expect(page.get_by_text("Checked source SHA-256: " + digest, exact=True).last).to_be_visible()
        with page.expect_download() as item:
            page.get_by_role("button", name="Download current checked RTL", exact=True).click()
        item.value.save_as(str(output / "checked.v"))
        assert (output / "checked.v").read_bytes() == expected
        with page.expect_download() as item:
            page.get_by_role("button", name="Download current-check evidence", exact=True).click()
        item.value.save_as(str(output / "evidence.zip"))
        with zipfile.ZipFile(output / "evidence.zip") as archive:
            manifest = json.loads(archive.read("manifest.json"))
            assert len(archive.namelist()) == len(manifest) + 1
            for name, entry in manifest.items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == entry["sha256"]
            assert archive.read("record/candidate.v") == expected
            assert "sealed_case/LICENSE" in manifest and "MODIFICATIONS.md" in manifest
            assert "sealed_case/trace_2/expected.hex" in manifest
            assert "checker_source/rtl_agent__known_bugs_v2__engine.py" in manifest
            assert "ARTIFACT-LICENSE-BSD-3-Clause.txt" in manifest
            assert not any("obj_dir" in n or "controls_after_inference" in n or ".env" in n for n in manifest)
        page.get_by_role("button", name="Download current checked RTL", exact=True).scroll_into_view_if_needed()
        page.screenshot(path=str(output / "02_fresh_feedback_only_repair.png"))
        editor = page.get_by_role("textbox", name="Editable known-case RTL", exact=True)
        editor.fill("module changed; endmodule");editor.press("Tab")
        expect(page.get_by_text("Source changed. Run checks on the applied edits before using a prior result.", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="Download current checked RTL", exact=True)).to_have_count(0)
        page.get_by_text("Oracle validity", exact=True).click()
        page.get_by_text("V1 development correction", exact=True).click()
        expect(page.get_by_text("The v1 interpretation of a harmful normal-code rewrite was withdrawn", exact=False)).to_be_visible()
        page.screenshot(path=str(output / "03_oracle_scope_correction.png"))
        browser.close()
    assert ledger == (ROOT / ".state/spend.json").read_bytes()
    assert not errors
    result = {"status": "PASS", "new_model_calls": 0, "browser_errors": errors, "paired_metrics_match_frozen_result": True,
              "fresh_feedback_only_repair_reproduced": True, "exact_source_and_evidence_hashes": True,
              "license_and_corrected_trace_scope_in_export": True, "v1_interpretation_withdrawn_and_oracle_scope_visible": True,
              "edited_source_invalidates_previous_pass": True}
    (output / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
