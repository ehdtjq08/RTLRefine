# Synthetic fault challenge without a fixed RTL oracle

This extension deliberately injects faults. It is **not** a claim of newly found
real-world defects, an external held-out benchmark or a new verification theorem.
The previous historical cases and their frozen 3/9 versus 2/9 comparison remain
separate and unchanged.

## What is sealed before repair inference

One project-authored ready/valid queue has a public behavioral contract and
immutable interface. Eight shuffled variants include five single-fault operators,
one combined write/reset fault, a normal control and a functionally equivalent
normal control. The operators affect write acceptance, read advancement, reset
tail state, full-capacity admission and LAST/USER association.

The repair model receives one candidate and the contract in an isolated API
context. It receives no pristine implementation, mutation name, location or edit
map for an injected case. The source and label hashes, checker, model settings,
profiles and two-request cap are sealed before requests. Labels are joined only
after all inference for reporting. Constructed controls have their own independent
contexts; they are not offered as reference implementations to faulty cases.

## Independent scoring

The evaluator reads the public interface, contract and candidate. It never loads
the pristine RTL or mutation map. Python reconstructs a deque from accepted
interface transactions. A separate formal monitor uses a transaction-level shift
queue instead of the DUT's circular memory pointers.

The properties require correct valid/occupancy, ready/capacity, payload order,
sidebands, stalled-output stability and no excess capacity. Ready and valid cannot
be tied off to get a vacuous pass. The monitor selects an arbitrary payload or
sideband bit and holds that selector constant across the proof bound. It constrains
the range to all 10 bits; it does not fix a convenient bit. Both ready/valid and
full-word stability obligations are checked as well.

Formal assumptions are explicit: initial reset, legal stable source while stalled,
and a stable selected bit. Receiver ready is otherwise unconstrained. Unspecified
initial state is zero in the two-state proof. The profiles are 2 words / 16 steps
and 4 words / 12 steps. A 4-word / 20-step clean calibration timed out and remains
UNPROVEN; the smaller final profile was fixed before any repair-model outcome.

Three discovery simulations and three unexposed audit simulations use capacities
2, 4 and 8 with different seeds, repeated resets, full stalls, simultaneous
enqueue/dequeue, sideband variation and a finite drain window. The audit
observations never enter feedback, and audit failure cannot trigger an extra
model call. Only the discovery simulations and public formal properties determine
whether the second repair request is made.

SAT input traces are replayed through Icarus and the Python queue. Replay is
reported only when the same input sequence reproduces a contract failure. Four-state
uninitialized-memory values can differ from the SAT zero-state model; this is
reported rather than described as identical internal-state replay.

## Calibration and reporting

Before inference, all six injected candidates failed both formal profiles and
directed checks; the two normal controls passed. Twelve SAT input witnesses
reproduced contract failures in Icarus. This qualifies the scorer on the designed
mutations, not on arbitrary bugs. Model outcomes are recorded separately.

The completed report retains every attempt, including malformed outputs, policy
failures and incomplete proofs. Healthy cases are reported as healthy controls,
not successful bug repairs. Unnecessary repair decisions on controls remain
visible. No model source is manually corrected before acceptance.

## Executed NVIDIA outcome

The frozen run completed 11 actual inference requests, estimated at $0.226926.
All six injected cases obtained an accepted repair within the two-request cap.
Four were accepted on the first request; two required a second request after a
policy rejection. Each accepted file passed three discovery simulations, three
unexposed audit simulations and both property profiles without manual correction.
All three initial policy failures remain recorded, including one on a control.

One normal control was kept functionally unchanged. The other received an
unnecessary repair decision and a token-changing rewrite that still passed the
contract. It is reported as over-repair, not a successful bug fix. The interactive
workflow disables AI repair for a current input that already passes the checks.

These results do not erase the earlier historical cohort's lack of feedback
advantage. The tasks, oracle and protocols differ; counts are not pooled.

Run `python3 -m streamlit run rtl_app.py` and select **Synthetic property challenge**.
The `/mutation` view supports inspection, source edits, fresh property checks,
counterexample replay and evidence export. Live NVIDIA repair is optional and
uses the same persistent budget ledger.

This demonstrates conformance checks against an explicit specification without a
fixed corrected implementation. It does not infer requirements from nothing,
prove all configurations or times, establish a general repair success rate, or
replace independent designer evaluation.

Formal background for solver-selected constants and assumptions:
https://yosyshq.readthedocs.io/projects/sby/en/latest/verilog.html
