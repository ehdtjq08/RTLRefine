# External historical UART: CTS after BREAK

This case comes from **ZipCPU/wbuart32**, written by Gisselquist Technology,
independently of RTLRefine and the previously used verilog-axis project. It is a
selected public historical defect, not a newly discovered bug, injected mutation,
unseen benchmark, general success-rate estimate or algorithm comparison.

The original transmitter briefly deasserts `o_busy` after BREAK recovery even
when active-low CTS has continuously blocked transmission. A legal source that
writes only when `!o_busy` can therefore start sending a byte against the
receiver's flow-control request. The original fails this twice per flow-enabled
simulation. The corrected transmitter remains busy until CTS permits a new byte.

Upstream fix: [07e4c47](https://github.com/ZipCPU/wbuart32/commit/07e4c47166f0407c276bee571900ed2f9df06bad),
2019-02-21. Buggy parent: `f0e785d7329fdebbfa2476e9b8b0d5797a1d081d`.
Raw sources, specification and hashes are in `third_party/wbuart32_cts/source.json`.
Vendor and derived RTL retain **GPL-3.0-or-later**, original notices and full
corresponding source. The project's MIT license does not replace this license.

## Independent admission

`rtl_agent/uart_external` never reads corrected RTL or compares candidate output
with a maintained implementation. It receives a source string and checks public
ports against a behavioral contract:

- Six discovery simulations: three baud/format profiles, flow enabled and disabled.
- Six unexposed audit simulations at other baud/format/seed combinations.
- Every simulation checks all cycles of 24 accepted serial frames: start bit,
  LSB-first data, configured fixed parity, stop bits and forward progress.
- Two BREAK episodes check blocked CTS; disabled-flow controls reject the vacuous
  solution of permanently holding busy high.
- CTS safety properties check arbitrary reset/BREAK timing for divisor 4 / 80
  symbolic steps and divisor 5 / 96 steps. Unspecified state is zero, explicit
  original initializers retained, first step resets, configuration constant,
  CTS blocked and write disabled. Serial payload is checked separately in simulation.

The original fails all six flow-enabled checks, passes all six disabled-flow
controls, and produces two property counterexamples. Both exact external input
sequences reproduce the failure in four-state Icarus. The maintainer control
passes all twelve simulations and both property bounds. It qualifies the checker
before inference; it is never a runtime scoring oracle or a model input.

Pre-inference calibration also found a divisor-two forward-progress failure and
a computed-parity disagreement in the maintainer control. Both remain in
`demo/external_uart/excluded_mode_calibration`. The CTS contract was restricted
to divisors >=4 and no parity or fixed mark/space parity **before model outcomes**.
There is no correctness claim for excluded modes, all configurations, unbounded
operation, CDC/metastability or physical-board behavior.

## Actual NVIDIA development outcome

All **4 actual Nebius Token Factory requests** remain recorded. Estimated total
cost from reported usage: **$0.174519**. Rechecking made no additional requests.

1. The first response incorrectly declared the original healthy (`keep`);
   independent checks rejected that decision.
2. The feedback response exhausted its 16,384-token limit. No complete proposal
   was admitted or recovered from partial text.
3. A separately declared no-thinking recovery proposed a nonmatching edit to
   commented initialization. The controller rejected it without repairing it.
4. A separately declared compact-context request omitted the disabled upstream
   FORMAL appendix and returned the complete production body. It diagnosed the
   BREAK recovery path and gated busy with synchronized CTS. The exact raw body
   was joined with the unchanged original interface/license and disabled appendix.

The fourth source initially hit a **controller bug**: the boundary finder
required a leading tab before the first wire declaration. The returned body
omitted that indentation. The original rejection is retained. The boundary
parser alone was corrected to accept equivalent leading whitespace; simulation,
properties, initial-state requirements and execution sandbox were unchanged.
Original and maintainer controls were requalified before rechecking the exact
same model source. No functional manual repair was inserted.

The final recheck passes **12/12 simulations and 2/2 bounded CTS properties**,
checking **288 complete serial frames** across those simulations. Source SHA-256:
`9befd29188fd1f88cd232ebda3df255f71b1747ffba2a88c3cf98dc1411a4581`.
`demo/external_uart/run/BOUNDARY_RECHECK.json` and the exact parser diff disclose
the post-hoc correction. **This is not a prospectively frozen four-request
success**. It is not pooled into the synthetic cohort or nine-pair comparison.
Training contamination from public source cannot be excluded. One verified
external repair does not establish an accuracy advantage from feedback.

## Inspect and rerun

Run `python3 -m streamlit run rtl_app.py`, then open `/uart`. The page shows
the original failure, all four model outcomes, parser correction and final checks.
Its editable workspace reruns the exact current source in bubblewrap. Browsing
and verification make zero model requests. Downloads include checked RTL, GPL
license, modification notice, observed ports, checkers, scripts, scope and hashes.
Editing invalidates an earlier pass.

With pinned EDA tools installed, these commands make no paid requests:

```sh
python3 -m pytest -q tests/test_external_uart.py
python3 -m scripts.qualify_external_uart
```

Raw contexts/responses, old checker snapshots, calibration failures and controls
are bundled for audit. Optional new requests use the persistent budget ledger and
Nebius key; stochastic results are not exact reproductions of the recorded run.

Public repository, hosting, YouTube upload, Devpost submission and a human
usability study remain incomplete.
