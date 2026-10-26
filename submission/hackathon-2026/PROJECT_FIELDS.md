# Project name

RTLRefine: Checked RTL Repair

# Elevator pitch

Repair RTL with NVIDIA Nemotron on Nebius, run your own testbenches, and download the exact source that passes independent checks.

# Track

Coding and Agentic Engineering

# Built with

Nebius Token Factory, NVIDIA Nemotron 3 Ultra, Python, Streamlit, Icarus Verilog,
Verilator, Yosys, C++, Bubblewrap, Docker.

# Source code URL

https://github.com/ehdtjq08/RTLRefine

# Try it / test build URL

https://github.com/ehdtjq08/RTLRefine/blob/v1.2.1/docs/JUDGE_QUICKSTART.md

This is a downloadable Docker test build, not a hosted application. The page
links the versioned source download and explains credential-free verification.

# Video URL

Upload video/RTLRefine-demo.mp4 to YouTube with visibility set to Public, then
paste the resulting YouTube URL here. A GitHub MP4 link does not replace the
required YouTube link.

# Testing instructions

Download the tagged test build and run `docker compose up --build` on a Linux
Docker host that permits unprivileged user namespaces. Open
http://127.0.0.1:8501. No API key is needed to inspect recorded NVIDIA repairs,
recheck their exact source, or check an uploaded RTL project. The project route
is /project; a verification walkthrough is in docs/JUDGE_QUICKSTART.md.

The default build disables new paid requests. Actual Nebius requests are shown
in the video and retained with their responses. Fresh inference requires an
operator-supplied server-side credential; it is not provided in this test build.

# About the project

Paste DEVPOST_ABOUT.md.

# Nebius / NVIDIA feedback

Paste NEBIUS_FEEDBACK.md into the feedback field.
