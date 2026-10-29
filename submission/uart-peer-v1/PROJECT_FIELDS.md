# Project name

RTLRefine: Checked RTL Repair

# Elevator pitch

Repair RTL with NVIDIA Nemotron on Nebius, independently check the patch, and export executable regressions that catch the bug if it returns.

# Track

Coding and Agentic Engineering

# Built with

Python, Verilog, SystemVerilog, C++, Streamlit, Nebius Token Factory,
NVIDIA Nemotron, Icarus Verilog, Verilator, Yosys, Bubblewrap, Docker, GitHub Actions.

# Source code URL

https://github.com/ehdtjq08/RTLRefine

# Try it out / test build

https://github.com/ehdtjq08/RTLRefine/blob/v1.6.2/docs/JUDGE_QUICKSTART.md

# Video URL

Upload `video/RTLRefine-UART-peer-demo.mp4` to YouTube as Public and paste its new
URL here. This is the latest continuous normal-speed video. The earlier
https://youtu.be/JEvktXDIUd0 does not show these current features.

# Testing instructions

Build the tagged Docker source. Open /external-validation and its UART serial
peers tab. Reproduce the original's limited loopback PASS, its independent-peer
failure, the selected actual NVIDIA repair's fresh recheck and the exported
0→1→0 CI cycle. All these actions use zero model requests. Download the checked
ZIP and recheck it in /project or run `python3 -I rtlrefine_ci/run.py` after
extracting it. /properties demonstrates a separate authored FIFO contract and
independently replayed counterexample. Fresh inference requires an operator's
credential and is disabled by default; recorded actual responses are included.

# About and feedback

Paste DEVPOST_ABOUT.md and NEBIUS_FEEDBACK.md. This is a solo entry and uses I.
