# Suggested title

RTLRefine: Checked RTL Repair, Portable Regressions and Real External Validation

# Description

RTLRefine uses NVIDIA Nemotron on Nebius Token Factory to propose RTL edits,
independently checks them and exports reusable regressions. The NVIDIA results
shown are actual recorded runs, labeled accordingly; native checks and replays
run fresh. All three normal-speed UI segments are retained without speeding execution.

The additional segment shows a known upstream early-ready throughput regression
in verilog-axis, repaired with one actual request and passing eight benches /
30,493 assertions. A second author's unmodified ZipCPU skid buffer plus a
disclosed stateless metadata adapter passes eight profiles / 30,847 assertions
with no model request. These are finite simulations and exposed development
cases, not a new discovery, unbounded AXI proof or unseen model accuracy.

General projects now export a standalone checker and GitHub Actions workflow.
The final segment records a fresh native check, actual checked ZIP download and
the included workflow. JSON/JUnit reports use explicit pass/regression/setup
exit codes; no app installation, provider key or inference is needed.

Source: https://github.com/ehdtjq08/RTLRefine
Test build: https://github.com/ehdtjq08/RTLRefine/blob/v1.5.0/docs/JUDGE_QUICKSTART.md

Third-party source and licenses are preserved. No physical board, timing, power
or placed-and-routed area result is claimed. The separate historical 15x
screening measurement does not apply to these project-mode simulations.

Upload `video/RTLRefine-project-ci-demo.mp4` as Public. Use the new
YouTube URL in Devpost. English captions are embedded and provided as SRT.
