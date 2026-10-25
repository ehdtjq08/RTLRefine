"""Record the synthetic, reference-free challenge and fresh property verification."""
import argparse
import hashlib
import json
import shutil
import subprocess
import time
import zipfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def stamp(value):
    milliseconds = round(value * 1000)
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    ledger = (ROOT / ".state/spend.json").read_bytes()
    captions, errors = [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which("google-chrome"), headless=True, args=["--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, record_video_dir=str(output / "raw"),
                                      record_video_size={"width": 1440, "height": 1000}, accept_downloads=True)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        captured = time.monotonic()
        page.goto("http://127.0.0.1:8502/mutation", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="Repair the fault. Keep the contract.", exact=True)).to_be_visible(timeout=30000)
        start = time.monotonic()
        trim = start - captured

        def hold(text, seconds):
            begin = time.monotonic() - start
            print(f"Segment {begin:.1f}s: {text}", flush=True)
            page.wait_for_timeout(250 if args.preflight else int(seconds * 1000))
            captions.append((begin, time.monotonic() - start, text))

        def select(case_id):
            selector = page.get_by_test_id("stSelectbox").get_by_role("combobox")
            selector.click();page.get_by_role("option", name=case_id, exact=True).click()
            expect(selector).to_have_attribute("aria-label", __import__('re').compile(case_id))
            page.wait_for_timeout(350)

        hold("RTLRefine: synthetic queue faults, checked without a corrected RTL oracle.\nThe model results are real recorded Nebius calls; this video runs fresh checks.", 10)
        page.get_by_text("Read the public behavioral contract", exact=True).click()
        page.get_by_text("Read the public behavioral contract", exact=True).scroll_into_view_if_needed()
        hold("The oracle is an executable behavioral contract: ready/valid, reset, order and sidebands.\nIndependent Python deque and a formal shift-queue monitor never load pristine RTL.", 12)
        page.get_by_text("Read the public behavioral contract", exact=True).click()
        select("candidate_08")
        page.get_by_role("heading", name="Input candidate · specification check", exact=True).scroll_into_view_if_needed()
        expect(page.get_by_text("NOT ACCEPTED · SIMULATION_FAILED", exact=True)).to_be_visible()
        page.get_by_text("CONTRACT_FAILURE_REPRODUCED", exact=True).first.scroll_into_view_if_needed()
        hold("This candidate has two intentional faults. The model received no pristine source or edit map.\nSAT input witnesses reproduce contract failures in Icarus and an independent queue.", 17)
        page.get_by_role("heading", name="NVIDIA result · VERIFIED_AGAINST_SPEC_WITHIN_BOUND", exact=True).scroll_into_view_if_needed()
        hold("Nemotron Ultra repaired the candidate within the fixed two-request cap.\nEvery response is retained, including the first rejected proposal; no manual patch is inserted.", 15)
        page.get_by_role("tab", name="Edit and check RTL", exact=True).click()
        panel = page.get_by_role("tabpanel", name="Edit and check RTL", exact=True)
        panel.get_by_text("Recorded accepted repair", exact=True).click()
        panel.get_by_role("button", name="Run specification checks", exact=True).click()
        expect(panel.get_by_text("VERIFIED AGAINST SPEC WITHIN BOUND", exact=True)).to_be_visible(timeout=60000)
        panel.get_by_text("VERIFIED AGAINST SPEC WITHIN BOUND", exact=True).scroll_into_view_if_needed()
        expect(panel.get_by_test_id("stMetric").filter(has_text="Golden RTL used").get_by_test_id("stMetricValue")).to_have_text("No")
        hold("Fresh verification passes three discovery and three unexposed audit simulations.\nProperties pass for 2 words / 16 steps and 4 words / 12 steps; this is not unbounded proof.", 15)
        with page.expect_download() as item:
            panel.get_by_role("button", name="Download property-check evidence", exact=True).click()
        item.value.save_as(str(output / "property_evidence.zip"))
        with zipfile.ZipFile(output / "property_evidence.zip") as archive:
            for name, entry in json.loads(archive.read("manifest.json")).items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == entry["sha256"]
            assert "formal_0/properties.v" in archive.namelist() and "COPYING" in archive.namelist()
            assert not any(name.endswith(("clean.v", "mutation_map.json", ".vvp")) for name in archive.namelist())
        hold("Export exact checked bytes, observed transfers, property scripts, checker source and hashes.\nAudit observations never enter repair feedback or decide an extra model request.", 10)
        select("candidate_03")
        warning = page.get_by_text("Recorded experiment: this sealed input is a normal control.", exact=False)
        expect(warning).to_be_visible(timeout=30000);warning.scroll_into_view_if_needed()
        hold("All six injected cases were repaired in 11 requests, but one healthy control was over-repaired.\nOnly one of two controls was kept unchanged. This limitation is part of the result.", 14)
        page.get_by_role("heading", name="Repair the fault. Keep the contract.", exact=True).scroll_into_view_if_needed()
        hold("Eight constructed variants of one authored queue, with all attempts preserved.\nNo new real-world bug, general repair accuracy, external held-out result or first-algorithm claim.", 10)
        duration = time.monotonic() - start
        raw = Path(page.video.path());context.close();browser.close()
    assert not errors and ledger == (ROOT / ".state/spend.json").read_bytes()
    report = {"status": "PASS", "new_model_calls": 0, "browser_errors": errors, "synthetic_label_visible": True,
              "real_recorded_nebius_results": True, "fresh_specification_checks": True, "no_fixed_rtl_oracle": True,
              "over_repair_on_healthy_control_disclosed": True, "download_manifest_verified": True, "capture_seconds": duration}
    if not args.preflight:
        assert duration < 177
        with (output / "captions.srt").open("w") as file:
            for i, (begin, end, text) in enumerate(captions, 1):
                file.write(f"{i}\n{stamp(begin)} --> {stamp(end)}\n{text}\n\n")
        video = output / "RTLRefine-contract-demo.mp4"
        filters = "subtitles=captions.srt:force_style='FontName=DejaVu Sans,FontSize=17,Outline=1,Shadow=0,MarginV=16'"
        subprocess.run(["ffmpeg", "-y", "-ss", str(trim), "-i", str(raw), "-t", str(duration), "-vf", filters,
                        "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart", str(video)],
                       cwd=output, check=True, capture_output=True)
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video)], check=True, capture_output=True, text=True)
        report["video_seconds"] = float(json.loads(probe.stdout)["format"]["duration"])
        assert report["video_seconds"] < 180
        report["video_sha256"] = hashlib.sha256(video.read_bytes()).hexdigest()
    (output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
