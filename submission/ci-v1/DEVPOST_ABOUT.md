## Inspiration

A FIFO can pass its smoke test and still miscount when enqueue and dequeue happen
together. Even after a repair, that bug can return in a later edit. I wanted a
tool that could find the missing case, check an AI-proposed correction, and leave
the designer with executable tests that remain useful outside the application.

## What it does

RTLRefine repairs Verilog/SystemVerilog using NVIDIA Nemotron through Nebius
Token Factory. Users can upload sources and their own benches. The browser can
configure file roles and inspect actual FIFO ports without requiring JSON files.
Designers can also edit permitted logic and rerun the same verification gates.

For a supported synchronous FIFO contract, RTLRefine finds and minimizes a
symbolic counterexample, then reproduces it in Icarus against an independent
Python queue. Nemotron receives the public contract, failure and compiler feedback
to propose edits. Final audit source and results remain withheld until selection
is fixed, and a final rejection ends the run.

The checked ZIP includes self-checking regressions and a standalone Python runner.
One command recompiles the source without an API key or application installation.
Reintroducing the original defect makes the regressions fail. Reopening the ZIP
through either project route retains its FIFO checks and prior counterexamples.

General projects also export the existing checker as a small standalone bundle,
with JSON/JUnit reports and a GitHub Actions workflow. The exact exported runner
must pass before download. Later RTL edits are recompiled; protected tests and
configuration require review and a fresh export. No app installation or model
request is needed for these supplied-test checks.

## How I built it

Python and Streamlit coordinate Yosys, Icarus and isolated native workers. The
formal monitor tracks an arbitrary accepted transaction independently of the
DUT's circular addresses. Replay uses a separate full Python queue; no corrected
reference FIFO implementation is loaded.

Regression expectations come from the contract and inputs, not the failing DUT's
observed handshakes. Benches sample before and after the positive edge. The exact
exported runner must pass in isolated Python before download is enabled. Native
tools have readonly inputs, process limits, no network or API credentials, and
fresh completion markers. Uploaded Python is never executed.

The app also compares original and selected source under identical Xilinx
7-series synthesis settings. Logic LUT cells, registers and memory primitives
are separate estimates. This diagnostic does not replace correctness checks.

## Challenges I ran into

The first functional-extension pilot returned two broad edits that did not
compile. It exposed a feedback gap: the revision was missing the actual compiler
diagnostics. I retained both failures, added explicit compiler feedback and
clarified pre-edge versus post-edge state. A separate follow-up run succeeded.

Deeper property checks also exceeded time limits. Those results remain UNPROVEN.
The demonstrated profile uses 12 symbolic states for discovery and final bounds
16 and 20, including reset, plus a reachable-progress check. Invalid or incomplete
verification never becomes an accepted export.

## Accomplishments I'm proud of

- I reproduced a known upstream early-ready throughput regression in the real
  MIT-licensed verilog-axis AXI4-Stream register. One actual NVIDIA request
  repaired it; the exact source passed eight benches and 30,493 assertion
  evaluations, then passed again after export and reimport.
- A second independent author's unmodified ZipCPU skid buffer, with a disclosed
  stateless sideband adapter, passed eight profiles and 30,847 assertions without
  a model request. Both external scoreboards rejected explicit corruption controls.
- Three authored defects pass their smoke tests but have independently replayed
  failures in five, six and six symbolic states. A healthy control passes without
  requesting inference.
- The follow-up actual NVIDIA repair uses one request and passes four smoke
  expectations, 65 sequence checks, both deeper bounds and progress reachability.
- Its exported runner passes two regressions with 191 assertions. An independent
  command-line cycle returns exit codes **0 → 1 → 0** for checked source, the
  reintroduced defect and restored source.
- In this example, mapped logic LUT cells change from 12 to 11; seven register
  cells and one LUTRAM primitive remain unchanged. These are synthesis estimates.
- The existing historical screening engine separately measured 15.0x throughput
  for the same 118 candidates, one paired run per profile. That result does not
  apply to the independently compiled property/regression workflow.

The general CI exports also reproduce **0 → 1 → 0** for checked source, a
reintroduced bug and restored source across the prior external patch and two
authored healthy integration fixtures. Editing a protected audit returns a setup
error instead. These are regression demonstrations, not additional AI repairs.

## What I learned

Failure evidence needs to survive the repair. Exporting a source file and a
reusable regression suite makes the result easier to review and maintain.
Compiler errors also need to reach the agent as concrete feedback.

The external early-ready case is a known historical throughput/capacity issue,
not a new discovery or an unconditional AXI protocol violation. I inspected
upstream history for qualification; corrected source was not a model input or
acceptance oracle. Parent, revert and current healthy files have identical hashes
and count as one implementation.

The verification contract still defines the guarantee. These FIFO fixtures are
authored integration demonstrations, not unseen repair accuracy. Bounded checks
and finite regressions do not establish unbounded correctness, physical timing,
power or CDC safety. FIFO variants with different ready or latency behavior need
their own contracts.

## What's next for RTLRefine

I plan to evaluate independent users' projects, support additional protocol
contracts and improve verification scalability. Future comparisons will match
model and checking budgets and report failed attempts alongside accepted repairs.
