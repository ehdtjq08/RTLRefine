"""Record the current UI and one real, budget-limited user-project repair.

Run with the browser environment against an owner-enabled localhost instance.
The recording is continuous real time; captions occupy a separate lower band.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rtl_agent.project_repair.examples import example_files
from rtl_agent.budget import BudgetLedger


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pack(files, path):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)


def stamp(seconds):
    value = round(seconds * 1000)
    hours, value = divmod(value, 3600000)
    minutes, value = divmod(value, 60000)
    seconds, millis = divmod(value, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def ass_stamp(seconds):
    value = round(seconds * 100)
    hours, value = divmod(value, 360000)
    minutes, value = divmod(value, 6000)
    seconds, centis = divmod(value, 100)
    return f"{hours}:{minutes:02}:{seconds:02}.{centis:02}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8511")
    parser.add_argument("--output", default="submission/hackathon-2026")
    args = parser.parse_args()
    out = ROOT / args.output
    video_dir = out / "video"
    video_dir.mkdir(parents=True, exist_ok=False)
    examples = out / "examples"
    examples.mkdir(exist_ok=True)
    screens = out / "screenshots"
    screens.mkdir(exist_ok=True)
    files = example_files()
    files["LICENSE"] = (ROOT / "LICENSE").read_bytes()
    pack(files, examples / "wide-math-original.zip")
    partial = dict(files)
    partial["rtl/word_math.sv"] = partial["rtl/word_math.sv"].replace(
        b"combine = lhs - rhs;",
        b"combine = lhs[WIDTH-2] ? lhs - rhs : lhs + rhs;",
    )
    pack(partial, examples / "wide-math-partial.zip")
    budget_before = BudgetLedger().summary()
    captions, errors = [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=shutil.which("google-chrome"), headless=True,
            args=["--disable-dev-shm-usage", "--disable-gpu", "--renderer-process-limit=1"],
        )
        context = browser.new_context(
            viewport={"width": 1600, "height": 800},
            record_video_dir=str(video_dir / "raw"),
            record_video_size={"width": 1600, "height": 800},
            accept_downloads=True,
        )
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        captured = time.monotonic()
        page.goto(args.url, wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="An AI fix needs evidence.", exact=True)).to_be_visible(timeout=30000)
        start = time.monotonic()
        trim = start - captured

        pending_action = None

        def hold(text, seconds):
            nonlocal pending_action
            begin = time.monotonic() - start
            print(f"{begin:.1f}s: {text}", flush=True)
            page.wait_for_timeout(seconds * 1000)
            end = time.monotonic() - start
            if pending_action:
                action_begin, action_text = pending_action
                split = action_begin + min(6, (end - action_begin) / 2)
                captions.append((action_begin, split, action_text))
                begin = split
                pending_action = None
            captions.append((begin, end, text))

        def action(text, run):
            nonlocal pending_action
            begin = time.monotonic() - start
            run()
            pending_action = (begin, text)

        def show_result():
            page.get_by_role("heading", name="Project verification", exact=True).evaluate(
                "el => el.scrollIntoView({block: 'start', behavior: 'instant'})"
            )

        hold("RTLRefine: checked RTL repair with NVIDIA Nemotron on Nebius.\nInspect the failure, source diff and verification evidence in one browser.", 8)
        page.screenshot(path=str(screens / "01-repair-workspace.png"))
        page.goto(args.url + "/project", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="Bring your RTL. Bring your checks.", exact=True)).to_be_visible(timeout=30000)
        hold("Bring a Verilog/SystemVerilog ZIP and your own self-checking benches.\nSelect file roles in the browser, or include a manifest.", 8)
        page.locator("input[type=file]").set_input_files(str(examples / "wide-math-original.zip"))
        expect(page.get_by_text("DUT: customer_top", exact=False)).to_be_visible()
        page.get_by_text("Inspect submitted files", exact=True).click()
        page.get_by_test_id("stSelectbox").filter(has_text="File").get_by_role("combobox").click()
        page.get_by_role("option", name="rtl/word_math.sv", exact=True).click()
        page.get_by_test_id("stCode").scroll_into_view_if_needed()
        hold("This authored integration example has two files and a 129-bit function.\nIts result should be a+b, but the implementation subtracts.", 9)
        page.get_by_text("Inspect submitted files", exact=True).click()

        def original_check():
            page.get_by_role("button", name="Check this project", exact=True).click()
            expect(page.get_by_text("This source was not accepted: PUBLIC_TESTS_FAILED", exact=True)).to_be_visible(timeout=60000)

        action("First reproduce the public failure using isolated native tools.\nChecking the original makes no model request.", original_check)
        show_result()
        hold("The original fails its public test. No checked project is offered.\nThe tests remain immutable throughout the repair.", 7)

        def live_repair():
            page.get_by_role("button", name="Repair this project with NVIDIA", exact=True).click()
            expect(page.get_by_text("The exact project source passed every provided testbench.", exact=True)).to_be_visible(timeout=90000)

        action("A fresh NVIDIA request through Nebius Token Factory.\nThe model sees public checks; audit benches stay hidden.", live_repair)
        show_result()
        hold("Nemotron changes the subtraction to addition. The exact patch is rebuilt.\nBoth the public bench and the withheld 40-check audit pass.", 12)
        page.screenshot(path=str(screens / "02-nvidia-patch-and-checks.png"))
        with page.expect_download() as pending:
            page.get_by_role("button", name="Download checked project ZIP", exact=True).click()
        pending.value.save_as(str(examples / "wide-math-fixed.zip"))
        with page.expect_download() as pending:
            page.get_by_role("button", name="Download project evidence", exact=True).click()
        pending.value.save_as(str(video_dir / "live-project-evidence.zip"))
        with zipfile.ZipFile(video_dir / "live-project-evidence.zip") as archive:
            live = json.loads(archive.read("result.json"))
        assert live["accepted"] and 1 <= live["api_requests"] <= 2
        assert live["checked_archive_sha256"] == sha((examples / "wide-math-fixed.zip").read_bytes())
        assert live["changes"]["rtl/word_math.sv"].count("lhs + rhs") == 1
        assert all(t["status"] == "PASS" for t in live["final_check"]["tests"])

        def recheck_download():
            page.locator("input[type=file]").set_input_files(str(examples / "wide-math-fixed.zip"))
            expect(page.get_by_role("button", name="Download checked project ZIP", exact=True)).to_have_count(0)
            page.get_by_role("button", name="Check this project", exact=True).click()
            expect(page.get_by_text("The exact project source passed every provided testbench.", exact=True)).to_be_visible(timeout=60000)

        action("Reimport the exported ZIP and run both benches again.\nThis fresh check makes no model request.", recheck_download)
        show_result()
        hold("The exported project passes again. Its evidence includes logs and hashes.\nOriginal test files and the project license are preserved.", 8)

        page.locator("input[type=file]").set_input_files(str(examples / "wide-math-partial.zip"))
        expect(page.get_by_role("button", name="Download checked project ZIP", exact=True)).to_have_count(0)
        hold("Now upload an intentionally incomplete developer-written patch.\nChanging the project removes the previous successful verdict immediately.", 8)

        def reject_partial():
            page.get_by_role("button", name="Check this project", exact=True).click()
            expect(page.get_by_text("This source was not accepted: PROVIDED_TESTS_NOT_PASSED", exact=True)).to_be_visible(timeout=60000)
            expect(page.get_by_role("button", name="Download checked project ZIP", exact=True)).to_have_count(0)

        action("The partial patch passes the public bench and fails the audit.\nA checked download is blocked.", reject_partial)
        show_result()
        hold("Rejected with the failing observations retained.\nAcceptance covers only the supplied tests, not unbounded hardware correctness.", 10)
        page.screenshot(path=str(screens / "03-partial-patch-rejected.png"))
        page.goto(args.url, wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="An AI fix needs evidence.", exact=True)).to_be_visible(timeout=30000)
        page.get_by_text("Screening benchmark · measurement & scope", exact=True).click()
        metric = page.get_by_test_id("stMetric").filter(has_text="Measured complete-pool screening throughput")
        expect(metric).to_be_visible()
        metric.scroll_into_view_if_needed()
        hold("Historical examples: the same 118 candidates take 208.08s vs 13.87s.\n15.0x screening throughput; matching results, one paired run per profile.", 12)
        hold("This screening measurement does not apply to uploaded projects.\nTheir exact files are compiled independently using the supplied benches.", 8)
        page.screenshot(path=str(screens / "04-screening-measurement.png"))
        page.goto(args.url + "/project", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="Bring your RTL. Bring your checks.", exact=True)).to_be_visible(timeout=30000)
        hold("Public source and a Docker test build: github.com/ehdtjq08/RTLRefine\nRecorded NVIDIA runs and fresh native checks work without an API key.", 8)
        duration = time.monotonic() - start
        raw = Path(page.video.path())
        context.close()
        browser.close()
    assert not errors and duration < 177, (errors, duration)
    budget_after = BudgetLedger().summary()
    assert budget_after["requests"] - budget_before["requests"] == live["api_requests"]
    with zipfile.ZipFile(examples / "wide-math-fixed.zip") as archive:
        for name, data in files.items():
            if name not in live["changes"] and name != "rtlrefine.json":
                assert archive.read(name) == data, name
    (video_dir / "captions.srt").write_text("".join(
        f"{i}\n{stamp(a)} --> {stamp(b)}\n{text}\n\n"
        for i, (a, b, text) in enumerate(captions, 1)
    ))
    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,28,&H00F4F1EB,&H00F4F1EB,&H000B1117,&H000B1117,0,0,0,0,100,100,0,0,1,0,0,2,70,70,22,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    (video_dir / "captions.ass").write_text(ass_header + "".join(
        f"Dialogue: 0,{ass_stamp(a)},{ass_stamp(b)},Default,,0,0,0,," + text.replace("\n", r"\N") + "\n"
        for a, b, text in captions
    ))
    filters = (
        "scale=1920:960,pad=1920:1080:0:0:color=0x0b1117,"
        "ass=captions.ass"
    )
    video = video_dir / "RTLRefine-demo.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-ss", str(trim), "-i", str(raw), "-t", str(duration),
        "-vf", filters, "-an", "-c:v", "libx264", "-threads", "2", "-preset", "fast",
        "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart", str(video),
    ], cwd=video_dir, check=True, capture_output=True)
    probe = json.loads(subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height,codec_name",
        "-of", "json", str(video),
    ], check=True, capture_output=True, text=True).stdout)
    seconds = float(probe["format"]["duration"])
    assert seconds < 180
    report = {
        "status": "PASS", "video_seconds": seconds, "video_sha256": sha(video.read_bytes()),
        "resolution": "1920x1080", "actual_current_ui": True,
        "continuous_real_time_recording": True, "new_model_calls": live["api_requests"],
        "model": "nvidia/Nemotron-3-Ultra-550b-a55b", "live_result_directory": live["directory"],
        "exported_project_reimported_and_rechecked": True, "immutable_test_files_and_license_preserved": True,
        "authored_partial_patch_public_pass_audit_fail": True, "rejected_checked_download_absent": True,
        "screening_measurement_scope_disclosed": True, "english_captions": True,
        "captions_in_separate_lower_band": True, "raw_trim_seconds": trim,
        "browser_errors": errors, "youtube_publication_complete": False,
        "estimated_inference_cost_usd": round(budget_after["accounted_usd"] - budget_before["accounted_usd"], 6),
    }
    (video_dir / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
