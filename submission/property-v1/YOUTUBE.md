# Suggested title

RTLRefine: Find and Repair RTL Bugs That Pass Their Tests

# Description

RTLRefine combines NVIDIA Nemotron on Nebius Token Factory with independent RTL
checks. This actual application recording shows a FIFO that passes its smoke test,
a five-state symbolic counterexample reproduced in Icarus against a Python
queue, a real NVIDIA repair and fresh verification of the exported project.
The live run is shown at normal speed, followed by an additional close-up of
the same recorded patch and its final checks. No execution is sped up.

Source: https://github.com/ehdtjq08/RTLRefine
Docker test build:
https://github.com/ehdtjq08/RTLRefine/blob/v1.3.0/docs/JUDGE_QUICKSTART.md

The examples are authored integration cases. The default FIFO contract uses
one positive-edge clock, synchronous reset, four-bit data and capacity four,
with final checks at bounds 16 and 20. These are bounded checks, not an unbounded
correctness, timing or physical CDC guarantee. Other FIFO latency/ready policies
need a different contract. No corrected reference FIFO is used by the verifier.

The separate 15x historical screening result does not apply to this workflow.
Recorded requests, failures, scope and exact source hashes are retained. The
default test build supports recorded-run review and new native checks without
an API key; fresh inference requires an operator credential.

# Upload

Upload `video/RTLRefine-independent-properties-demo.mp4` to YouTube as Public.
Use its new URL in Devpost's video field. Add the English subtitle file
`video/captions.srt` if desired; captions are already embedded in the MP4.
