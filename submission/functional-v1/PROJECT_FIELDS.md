# Project name

RTLRefine: Checked RTL Repair

# Elevator pitch

Repair RTL with NVIDIA Nemotron on Nebius, independently check the patch, and export executable regressions that catch the bug if it returns.

# Track

Coding and Agentic Engineering

# Built with

Python, Verilog, SystemVerilog, C++, Streamlit, Nebius Token Factory,
NVIDIA Nemotron, Icarus Verilog, Verilator, Yosys, Bubblewrap, Docker.

# Source code URL

https://github.com/ehdtjq08/RTLRefine

# Try it out / test build

https://github.com/ehdtjq08/RTLRefine/blob/v1.4.0/docs/JUDGE_QUICKSTART.md

# Video URL

Upload `video/RTLRefine-functional-demo.mp4` to YouTube as Public and paste its
new URL here. The earlier video https://youtu.be/JEvktXDIUd0 shows the preceding
workflow; it does not show this regression-export update.

# Testing instructions

Use the tagged Docker build and open /properties. Find the original failure,
run its failing regressions, inspect the recorded actual NVIDIA repair, and run
the exported standalone suite. No API key is needed. The uploaded-project route
is /project; exported FIFO projects keep their regressions through both routes.
New inference is disabled by default and requires an operator credential.

# About and feedback

Paste DEVPOST_ABOUT.md and NEBIUS_FEEDBACK.md. About uses I for the solo entry.
