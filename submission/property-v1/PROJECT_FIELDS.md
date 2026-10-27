# Project name

RTLRefine: Checked RTL Repair

# Elevator pitch

Repair RTL with NVIDIA Nemotron on Nebius, expose failures missed by tests, and independently check the exact project before export.

# Track

Coding and Agentic Engineering

# Built with

Python, Verilog, SystemVerilog, C++, Streamlit, Nebius Token Factory,
NVIDIA Nemotron, Icarus Verilog, Verilator, Yosys, Bubblewrap, Docker.

# Source code URL

https://github.com/ehdtjq08/RTLRefine

# Try it out / test build

https://github.com/ehdtjq08/RTLRefine/blob/v1.3.0/docs/JUDGE_QUICKSTART.md

# Video URL

The existing video is https://youtu.be/JEvktXDIUd0 . It shows the preceding
user-project workflow. Upload `video/RTLRefine-independent-properties-demo.mp4`
to YouTube, set it to Public, and use its new URL to show the FIFO extension.

# About the project

Paste DEVPOST_ABOUT.md. It uses I throughout for the solo entry.

# Testing instructions

Run the tagged Docker test build using docs/JUDGE_QUICKSTART.md. Open
http://127.0.0.1:8501/properties, reproduce the original independent failure,
inspect the saved actual NVIDIA repair and recheck its exported ZIP. No API
key is needed for those actions. The uploaded-project workflow remains at
/project. New inference is disabled by default and requires an operator key.

# Tool feedback

Paste NEBIUS_FEEDBACK.md.
