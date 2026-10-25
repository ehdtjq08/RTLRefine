"""Record the actual focused RTL app, with fresh verification and honest captions."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time
import zipfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def stamp(seconds):
    milliseconds = round(seconds * 1000)
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
    before = (ROOT / ".state/spend.json").read_bytes()
    captions, errors = [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which("google-chrome"), headless=True, args=["--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, record_video_dir=str(output / "raw"),
                                      record_video_size={"width": 1440, "height": 1000}, accept_downloads=True)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        captured = time.monotonic()
        page.goto("http://127.0.0.1:8502", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="An AI fix needs evidence.", exact=True)).to_be_visible(timeout=30000)
        start = time.monotonic()
        trim = start - captured

        def hold(text, seconds):
            begin = time.monotonic() - start
            print(f"Segment {begin:.1f}s: {text}", flush=True)
            page.wait_for_timeout(250 if args.preflight else int(seconds * 1000))
            captions.append((begin, time.monotonic() - start, text))

        def select_case(label):
            page.get_by_test_id("stSelectbox").get_by_role("combobox").click()
            page.get_by_role("option", name=label, exact=True).click()
            expect(page.get_by_test_id("stSelectbox").get_by_role("combobox")).to_have_attribute("aria-label", re.compile(re.escape(label)))
            page.wait_for_timeout(400)

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
            page.get_by_role("heading", name="Independent review result", exact=True).scroll_into_view_if_needed()

        good = "VERIFIED WITHIN BOUND · Every directed regression and bounded comparison passed."
        hold("RTLRefine: inspect an AI-generated RTL fix before keeping it.\nNVIDIA model calls shown here are recorded; the RTL checks run freshly in this video.", 7)
        page.get_by_role("link", name="Inspect three real historical RTL bugs", exact=True).click()
        expect(page.get_by_role("heading", name="Three real RTL failures.", exact=True)).to_be_visible(timeout=30000)
        select_case("Frame FIFO backpressure")
        expect(page.get_by_test_id("stMetric").filter(has_text="Valid bytes preserved").get_by_test_id("stMetricValue")).to_have_text("16 → 24")
        hold("A real upstream frame FIFO loses eight of 24 bytes during repeated receiver pauses.\nThe independently checked maintainer fix is a control, not a model-generated repair.", 14)
        page.goto("http://127.0.0.1:8502/workspace", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="Check your RTL change.", exact=True)).to_be_visible(timeout=30000)
        run_check("NOT ACCEPTED · SIMULATION_FAILED")
        hold("The editable workspace reproduces a different real bug: reset fails to flush old FIFO traffic.\nThree clock/occupancy regressions independently check stale and fresh transfers.", 11)
        page.get_by_text("Recorded NVIDIA candidate", exact=True).click()
        run_check(good)
        hold("A real Nemotron Ultra repair from Nebius passes fresh simulations and a 16-step comparison.\nThe known maintainer source was excluded from the model prompt.", 14)
        current = json.loads((ROOT / "demo/fifo_reset/current.json").read_text())
        source = (ROOT / "demo/fifo_reset" / current["accepted_rtl"]).read_text()
        edited = source + "\n// Designer review copy: unchanged logic, new checked file identity.\n"
        page.get_by_role("textbox", name="RTL source", exact=True).fill(edited)
        page.get_by_role("textbox", name="RTL source", exact=True).press("Tab")
        expect(page.get_by_text("The source changed.", exact=False)).to_be_visible()
        page.get_by_text("The source changed.", exact=False).scroll_into_view_if_needed()
        hold("Editing the source makes an older result inapplicable to the new bytes.\nRecheck the working copy before exporting it as verified.", 8)
        run_check(good)
        expect(page.get_by_text("Reviewed source SHA-256: " + hashlib.sha256(edited.encode()).hexdigest(), exact=True)).to_be_visible(timeout=60000)
        with page.expect_download() as download:
            page.get_by_role("button", name="Download this review's evidence", exact=True).click()
        download.value.save_as(str(output / "review_evidence.zip"))
        with zipfile.ZipFile(output / "review_evidence.zip") as archive:
            for name, entry in json.loads(archive.read("manifest.json")).items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == entry["sha256"]
            assert archive.read("candidate.v").decode() == edited
            assert "COPYING" in archive.namelist()
        hold("Export the exact checked RTL with observed traces, proof scope, controller source and MIT notices.\nThis review called no model and required no physical FPGA.", 8)
        select_case("AXI byte validity")
        run_check("NOT ACCEPTED · SIMULATION_FAILED")
        expect(page.get_by_test_id("stMetric").filter(has_text="Simulation regressions").get_by_test_id("stMetricValue")).to_have_text("4/6")
        hold("A partial NVIDIA fix passes same-width tests but still loses valid bytes when widening.\nFour of six regressions is a rejection, not a successful repair.", 12)
        select_case("Frame FIFO backpressure")
        run_check("NOT ACCEPTED · FORMAL_UNPROVEN_OR_FAILED")
        expect(page.get_by_test_id("stMetric").filter(has_text="Simulation regressions").get_by_test_id("stMetricValue")).to_have_text("3/3")
        hold("Another NVIDIA proposal passes all three directed tests but fails bounded reference comparison.\nThe gate requires both; reference agreement includes timing at the fixed parameters.", 12)
        page.goto("http://127.0.0.1:8502/comparison", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="Measure what the feedback changes.", exact=True)).to_be_visible(timeout=30000)
        expect(page.get_by_test_id("stMetric").filter(has_text="Self-review accepted").get_by_test_id("stMetricValue")).to_have_text("3/9")
        hold("Nine paired trials share the first proposal and the same two-call cap.\nSelf-review accepts 3/9; checker feedback 2/9. This cohort shows no feedback advantage.", 15)
        page.goto("http://127.0.0.1:8502", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="An AI fix needs evidence.", exact=True)).to_be_visible(timeout=30000)
        hold("Supported scope: three pinned historical modules, directed tests and bounded two-state checks.\nNo unbounded proof, designer time-saving study, hardware result or new-debugger claim.", 10)
        duration = time.monotonic() - start
        raw = Path(page.video.path())
        context.close()
        browser.close()
    assert not errors and before == (ROOT / ".state/spend.json").read_bytes()
    report = {"status": "PASS", "new_model_calls": 0, "browser_errors": errors, "fresh_rtl_verification": True,
              "recorded_model_proposals_labeled": True, "evidence_download_verified": True, "capture_seconds": duration}
    if not args.preflight:
        assert duration < 177
        with (output / "captions.srt").open("w") as file:
            for i, (begin, end, text) in enumerate(captions, 1):
                file.write(f"{i}\n{stamp(begin)} --> {stamp(end)}\n{text}\n\n")
        video = output / "RTLRefine-demo.mp4"
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
