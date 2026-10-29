# Suggested title

RTLRefine: When UART Loopback Passes but the Peer Gets the Wrong Byte

# Description

RTLRefine uses NVIDIA Nemotron on Nebius Token Factory to propose RTL edits,
checks the selected files independently and exports executable regressions.

This continuous normal-speed recording shows a known historical UART bit-order
case. The original TX/RX pair passes closed loopback yet reverses 0x01 into 0x80
against an explicit LSB-first peer. The actual recorded NVIDIA correction changes
both vendor files and passes eight profiles / 186,772 assertion evaluations.
All six development requests are retained; the last two-request run passed.

Native peer checks run fresh, followed by the exported CI command on checked,
original and restored source: exit codes 0 → 1 → 0. The same ZIP is rechecked in
the general project workspace. The final section shows a separate authored FIFO
example with an independently replayed symbolic counterexample and an earlier
actual recorded NVIDIA repair.

Recorded model results are labeled. Filming makes no new model request and
execution is never sped up. Checks are finite and contract-specific, not unseen
repair accuracy, new discovery, unbounded proof or physical timing/CDC results.
UART's author also wrote verilog-axis; no extra independent-author sample is
claimed. Original source and licenses are preserved.

Source: https://github.com/ehdtjq08/RTLRefine
Test build: https://github.com/ehdtjq08/RTLRefine/blob/v1.6.1/docs/JUDGE_QUICKSTART.md

Upload video/RTLRefine-UART-peer-demo.mp4 as Public and use the new URL in Devpost.
English captions are embedded in a separate band and included as SRT.
