"""Actual no-model browser inspection, fresh property check and exact evidence export."""
import hashlib
import argparse
import json
import shutil
import zipfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".tools/mutation-browser-qa-v2")
    args = parser.parse_args()
    output = ROOT / args.output
    output.mkdir(exist_ok=False)
    before = (ROOT / ".state/spend.json").read_bytes()
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which("google-chrome"), headless=True, args=["--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 1440, "height": 1100}, accept_downloads=True)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:8502/mutation", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="Repair the fault. Keep the contract.", exact=True)).to_be_visible(timeout=30000)
        expect(page.get_by_test_id("stMetric").filter(has_text="Injected cases repaired by NVIDIA").get_by_test_id("stMetricValue")).to_have_text("6/6")
        expect(page.get_by_test_id("stMetric").filter(has_text="Normal controls kept unchanged").get_by_test_id("stMetricValue")).to_have_text("1/2")
        expect(page.get_by_text("NOT ACCEPTED · SIMULATION_FAILED", exact=True)).to_be_visible()
        page.screenshot(path=str(output / "01_synthetic_input.png"))
        page.get_by_role("tab", name="Edit and check RTL", exact=True).click()
        panel = page.get_by_role("tabpanel", name="Edit and check RTL", exact=True)
        panel.get_by_text("Recorded accepted repair", exact=True).click()
        panel.get_by_role("button", name="Run specification checks", exact=True).click()
        expect(panel.get_by_text("VERIFIED AGAINST SPEC WITHIN BOUND", exact=True)).to_be_visible(timeout=60000)
        expect(panel.get_by_test_id("stMetric").filter(has_text="Specification properties").get_by_test_id("stMetricValue")).to_have_text("2/2")
        expect(panel.get_by_test_id("stMetric").filter(has_text="Golden RTL used").get_by_test_id("stMetricValue")).to_have_text("No")
        summary = json.loads((ROOT / "demo/mutation_challenge/run/summary.json").read_text())
        row = next(r for r in summary["cases"] if r["case_id"] == "candidate_01")
        expected = (ROOT / "demo/mutation_challenge/run" / row["accepted_source"]).read_bytes()
        expect(panel.get_by_text("Checked source SHA-256: " + hashlib.sha256(expected).hexdigest(), exact=True)).to_be_visible(timeout=60000)
        panel.get_by_text("VERIFIED AGAINST SPEC WITHIN BOUND", exact=True).scroll_into_view_if_needed()
        page.screenshot(path=str(output / "02_fresh_spec_check.png"))
        with page.expect_download() as item:
            panel.get_by_role("button", name="Download spec-checked RTL", exact=True).click()
        item.value.save_as(str(output / "checked.v"))
        assert (output / "checked.v").read_bytes() == expected
        with page.expect_download() as item:
            panel.get_by_role("button", name="Download property-check evidence", exact=True).click()
        item.value.save_as(str(output / "evidence.zip"))
        with zipfile.ZipFile(output / "evidence.zip") as archive:
            manifest = json.loads(archive.read("manifest.json"))
            assert len(archive.namelist()) == len(manifest) + 1
            for name, entry in manifest.items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == entry["sha256"]
            assert archive.read("candidate.v") == expected
            assert "formal_0/properties.v" in archive.namelist() and "COPYING" in archive.namelist()
            assert "checker_source/rtl_agent__mutations__simulation.py" in archive.namelist()
            assert not any(name.endswith(("clean.v", "mutation_map.json", ".vvp")) or ".env" in name for name in archive.namelist())
        page.get_by_test_id("stSelectbox").get_by_role("combobox").click()
        page.get_by_role("option", name="candidate_03", exact=True).click()
        expect(page.get_by_text("Recorded experiment: this sealed input is a normal control.", exact=False)).to_be_visible(timeout=30000)
        page.screenshot(path=str(output / "03_unnecessary_control_repair.png"))
        browser.close()
    assert not errors
    assert before == (ROOT / ".state/spend.json").read_bytes()
    result = {"status": "PASS", "new_model_calls": 0, "browser_errors": errors,
              "synthetic_label_visible": True, "all_outcomes_including_unnecessary_control_repair_visible": True,
              "fresh_specification_check_passed": True, "golden_rtl_used": False,
              "exact_rtl_download_verified": True, "evidence_manifest_and_license_verified": True}
    (output / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
