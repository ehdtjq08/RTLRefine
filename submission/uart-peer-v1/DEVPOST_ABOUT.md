## Inspiration

A passing test can provide false confidence. A FIFO smoke test can miss a
simultaneous-transfer error. A UART transmitter and receiver can exchange bytes
in loopback while sharing the wrong wire order for an external peer. I wanted
repairs checked against an explicit behavior contract, with failure evidence
that stays useful after the application is closed.

## What it does

RTLRefine uses NVIDIA Nemotron through Nebius Token Factory to propose
Verilog/SystemVerilog edits. Users upload sources and self-checking benches,
configure file roles in the browser, and inspect the exact source differences.
Only declared design files may change. Public execution failures guide at most
one revision; additional audit profiles run after selection is fixed.

An accepted general project exports a standalone checker, JSON/JUnit reports
and a GitHub Actions workflow. The exact exported script must pass before
download. Later RTL edits are compiled afresh, and a returning defect fails the
same checks without an application installation or model key.

For a supported synchronous FIFO contract, RTLRefine also finds a symbolic
counterexample beyond the uploaded smoke test, minimizes it and reproduces it
in Icarus against a separate Python queue. Those counterexamples become portable
regressions that remain attached when the project is reopened.

## How I built it

Python and Streamlit coordinate isolated Icarus, Yosys and native workers.
The general checker supports multiple files, functions, parameters, wide signals
and testbench-driven clocks. The FIFO monitor tracks an arbitrary accepted
transaction without relying on the DUT's circular addresses; replay uses an
independent transaction queue. Neither path loads corrected RTL as an oracle.

The UART demonstration uses commit-pinned, originally unmodified vendor TX/RX
modules and a disclosed stateless adapter. Independent peers generate expected
serial bits from offered bytes and expected received bytes from serial stimulus.
The public and audit benches share that monitor; seven additional parameter/seed
profiles stay outside model context. TX-only and RX-only controls must fail.

The exported checker bundles a byte-preserving copy of the existing native
verification engine and its license. Hashes bind the runner, checks and
configuration. Native execution has read-only inputs, resource limits, no network
or API credentials, and fresh completion markers. Uploaded Python is never
executed. Normal repository review protects intentional runner/workflow changes.

## Challenges I ran into

The UART development used six actual requests across three runs. The first run
repeated an incorrect diagnosis. The next run had a compilation failure and a
truncated reasoning revision. I preserved those failures, put the latest public
evidence after the rejected hypothesis, and allowed a bounded reasoning revision
with a larger completion cap. The last two-request run passed the unchanged
eight profiles and standalone runner. No final audit result guided a retry.

Before inference, the first UART bench did not compile because I used a reserved
SystemVerilog identifier. I retained that record and fixed the bench before
qualification. The maintainer control and both partial controls qualified the
monitor before any paid request. Deeper FIFO checks that exceeded their time
limit also remain unproven rather than becoming accepted exports.

## Accomplishments I'm proud of

- The historical UART pair passes its limited loopback smoke but reverses
  `0x01` into `0x80` against the declared peer. The selected NVIDIA TX/RX repair
  passes eight profiles and 186,772 assertion evaluations, including framing,
  overrun, reset and pending output behavior.
- A separate known verilog-axis early-ready throughput regression was repaired
  with one actual NVIDIA request and passed eight benches / 30,493 evaluations.
  Another author's unmodified ZipCPU skid buffer, with a disclosed adapter,
  passes eight healthy-control profiles without inference.
- Four checked exports reproduce **0 → 1 → 0** for checked source, a reintroduced
  defect and restored source. Editing a protected audit produces a setup error.
  The repository's GitHub Actions workflow runs the exported commands too.
- The authored FIFO example passes smoke tests but has a replayed five-state
  failure. Its earlier actual NVIDIA repair includes two portable regressions
  with 191 assertions and final checks at fixed bounds 16 and 20.

## What I learned

Self-consistency is weaker than agreement with the intended external behavior.
Failures also need to survive a repair: source hashes, immutable checks and an
executable regression make the result easier to review and maintain.

These are selected, exposed development cases, not an unseen accuracy benchmark
or a new bug discovery. The UART case is a known upstream MSB-first to LSB-first
change, not an introduced regression. Its author also wrote verilog-axis. I
inspected upstream history during qualification; training contamination cannot
be excluded. Changing prompts and token caps during development does not prove
a general advantage for reasoning or feedback.

The general route guarantees only its supplied finite tests. The FIFO route is
bounded and contract-specific. Neither establishes unbounded correctness,
physical timing, power or CDC safety.

## What's next for RTLRefine

I plan to observe independent designers using their own projects, support more
behavioral contracts and evaluate repair strategies with matched budgets and
predeclared cases. Failed attempts will remain part of those reports.
