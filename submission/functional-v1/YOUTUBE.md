# Suggested title

RTLRefine: Repair RTL and Export Tests That Catch the Bug Again

# Description

RTLRefine uses NVIDIA Nemotron on Nebius Token Factory to propose RTL repairs,
independently verifies the exact source, and exports self-checking regressions.

The NVIDIA repair shown is an actual recorded run, labeled in the interface.
Native diagnosis and standalone regressions run fresh in this normal-speed screen
recording. The original passes its smoke test but fails the independent check;
the checked repair passes the portable suite, and reintroducing the bug makes
it fail again. The export can be retested without an API key, Streamlit or Yosys.
Linux, Python, Icarus, bubblewrap and prlimit are required for the portable runner.

Source: https://github.com/ehdtjq08/RTLRefine
Docker test build:
https://github.com/ehdtjq08/RTLRefine/blob/v1.4.0/docs/JUDGE_QUICKSTART.md

These are authored integration examples with a stated synchronous FIFO contract,
not unseen repair accuracy or unbounded correctness. Final bounds are 16 and 20
symbolic states. Mapped logic LUT/register/memory counts are synthesis estimates,
not placed-and-routed area, timing, power or physical board measurements. The
earlier 15x candidate-screening result does not apply to this workflow.

Upload `video/RTLRefine-functional-demo.mp4` as Public and use its new YouTube URL
in Devpost. English captions are embedded; `video/captions.srt` is also available.
