# External AXI4-Stream register validation

This case uses unmodified Alex Forencich `verilog-axis/rtl/axis_register.v`,
with commit IDs, SHA-256 checksums and the upstream MIT license preserved in
`provenance.json`. It is a known upstream throughput/capacity regression, not
a new bug discovery or an unconditional AXI protocol violation.

Upstream commit `6d4458e5cc15df401b82a8fd615b3216e6a61d0e` simplified the early-ready
condition. Commit `b9e0af36341a81ae80d6a8467b029d79c69b71cb` reverted it for improved
throughput. The current source, pre-regression source and revert source have
identical file hashes; they are one distinct healthy implementation, not three
independent projects or accuracy samples.

## Oracle, qualified before inference

An independently authored transaction scoreboard checks accepted payload order,
enabled TKEEP/TLAST/TID/TDEST/TUSER, output stability under stalls, reset flushing,
bounded drain/conservation and buffering limits. Invalid payload bytes are masked
by TKEEP. Input payload and sidebands remain stable while input-valid is stalled.
No corrected RTL implementation generates expected outputs.

The public capacity test uses REG_TYPE=2's two-entry skid-buffer behavior. After
one accepted transfer and three input-idle cycles with output stalled, the second
slot must accept a transfer within four cycles. This captures the known loss of
useful skid capacity/throughput; it does not claim data corruption from that
upstream revision or require an arbitrary AXI receiver to assert READY.

Seven additional audit profiles cover skid/simple/bypass modes, data widths
8/16/32/64, enabled and disabled sidebands, full-rate transfers, input gaps,
backpressure, reset after traffic and independent deterministic seeds.

Before any model request, the current healthy source must pass all eight tests,
the regressed source must fail the public capacity test, and an explicitly
labeled test-harness data-corruption control must fail its data scoreboard.
The negative control alters only the observed test bus, not upstream RTL, and
is not an external bug discovery.

## Model and final acceptance

Use the ordinary uploaded-project workflow, with no module-name special case.
Only the regressed source and public bench/failure are sent to NVIDIA. Healthy,
parent and revert source and audit bench contents are absent from model context.
At most two bounded inference calls are allowed under the existing spend ledger.
After public selection, rebuild the exact candidate and run all eight profiles.
Final failure is terminal and cannot select or request another candidate.

The assistant inspected upstream history to choose and qualify this known case.
This is an exposed development evaluation, not a blinded or unseen model test.
Passing these finite tests does not establish unbounded AXI compliance, timing,
physical CDC safety or broad RTL repair superiority.
