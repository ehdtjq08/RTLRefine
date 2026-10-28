# Independent FIFO property repair: protocol fixed before model evaluation

This extension targets a single positive-edge clock, synchronous active-high
reset, ready/valid FIFO with no empty fall-through. The contract fixes capacity,
payload width and an explicit map from external ports. A positive result is
bounded evidence under that contract, not a proof for arbitrary FIFO variants.

The DUT must independently elaborate, expose exactly the mapped ports, and have
matching widths/directions. Numeric parameters and the contract are immutable.
Compiled state cells must use the same positive-edge clock; asynchronous state,
latches and multiple clocks are rejected. DUT assumptions, assertions, formal
attributes, checker hierarchy and simulator tasks are disallowed. Uploaded tool
scripts are not run. Native tools have no credentials or network access.

## Frozen demonstration cohort

The initial cohort consists of three **authored** integration defects and one
healthy control: incorrect occupancy on simultaneous push/pop, premature read
pointer wrap, and stale read pointer on reset. These are not new historical bug
discoveries and are not an unseen accuracy benchmark. The existing smoke bench
avoids those interactions and is expected to pass all four sources.

Before any model call, verify each defect has a reproducible independent-property
failure and the healthy control passes. Do not alter the evaluator or weaken
properties to admit a model proposal. Retain all unsuccessful attempts.

## Discovery, model boundary and acceptance

1. Run the existing public smoke bench with Icarus.
2. Yosys checks five external-port properties: valid/occupancy, ready/capacity,
   accepted payload order, output stability during stalls, and capacity.
3. Search 12 symbolic clock states (including the first reset state), with defined unconstrained
   inputs, zero initial state and reset in the first step. Binary-search the
   first failing bound; inconclusive results do not establish minimality.
4. Replay that exact input sequence in four-state Icarus against an independent
   Python transaction queue. Only a reproduced failure is given to the model.
5. NVIDIA may edit declared design files, with at most two bounded requests.
   Public tests and public counterexamples can guide one revision. The model
   receives no audit bench text, audit observations or audit depths.
6. Fix the selection before all final tests and bounds 16 and 20. An audit
   rejection is terminal. All original tests must pass and both deeper property
   checks must pass before exporting the exact project ZIP.
7. Require a reachable sequence containing enqueue, dequeue, full capacity,
   simultaneous transfers, output stall, a full queue-length of reads without an intervening reset,
   and reset after prior traffic. This is a progress check; it does not establish
   complete property adequacy.

The FIFO monitor universally tracks an arbitrary accepted transaction and its
number of predecessors, rather than copying the DUT's circular implementation.
The auxiliary `watch_this` input is unconstrained and does not enter the DUT;
the proof covers all of its choices. Progress also requires a watched dequeue.
The replay oracle is a separate full Python queue. Initial native-only trials
with a full shift-queue monitor exceeded the final-bound time limit; those
unproven records remain in results, and this monitor change precedes inference.
The planned 28-step final bound also exceeded a 45-second solve limit with both
SAT and an exploratory SMT engine. Before the first model request, the default
audit bounds were set to 16 and 20, which complete on the healthy control. The
28-step trials are retained as UNPROVEN, and no 28-step guarantee is claimed.
After the first integration run, the progress counter was strengthened to reset
its read count on reset, so the wrap stimulus cannot be satisfied by adding
reads from unrelated reset epochs. The initial run is retained separately;
current demonstrations and exports are revalidated with this stronger check.
Monitor, source, scripts, selected files and exported archives are hashed.
UNKNOWN, timeout, unsupported elaboration, unreproduced witness or unreachable
progress are never accepted as proofs. The prior 15x screening claim does not
apply to this independently compiled workflow.

## Initial inference budget

The existing persistent $50 total / $20 development accounting stays active.
The first demonstration is one repair of the simultaneous-transfer fixture,
at most two model requests. Any subsequent case/run is a separately recorded
development experiment; no hidden audit is recycled into a new selection.

Formal counterexample-guided refinement is an established method. This product
extension does not claim scientific novelty or general superiority. Further
quality comparisons require independent projects and matched budgets.

## v1.4 functional extension, specified before its inference run

Public counterexamples and an upfront contract sequence become self-checking
regressions. Expected state advances on transfers permitted by the contract,
not transfers observed from a buggy DUT. Benches sample before and after each
positive edge. A reproduced public property failure must also fail its generated
regression; a disagreement stops with an oracle-mismatch status.

Inherited regressions are immutable inputs and stay active through the generic
project route. Candidate feedback can add public counterexamples within the
existing two-request limit. No final audit is recycled into diagnosis. Selection
remains fixed before all original benches, deeper bounds, progress and a fresh
execution of the exact standalone regression script included in the export.

Only the canonical runner executes, in isolated Python; arbitrary uploaded
Python is never invoked. Native namespaces, readonly inputs, credential-free
environments and resource limits remain active. Fresh completion markers,
expected assertion counts and successful exits must agree. Timeouts and missing
completion are UNPROVEN, not counterexamples.

Original and selected source receive identical Xilinx 7-series synthesis
settings. Logic LUT cells, registers and memory/SRL/DSP primitives are separate
mapped estimates. This diagnostic does not alter correctness acceptance or imply
placement, routing, timing, power or board measurements. An unavailable mapper
does not invent counts or invalidate a separately checked functional result.
Historical source seals and comparison graders remain unchanged.

The first v1.4 development inference run produced two invalid broad line edits;
neither compiled, and no accepted export was created. Those public-only failures
are retained. Compiler diagnostics were then explicitly routed into revision
feedback, with pre-edge/post-edge state sampling explained and smaller edits
requested. This change uses no private audit observation and precedes the next
separately recorded development run; it is not an unseen accuracy comparison.
