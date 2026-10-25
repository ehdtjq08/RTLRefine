# RTLRefine

The **comparison lab** now provides the experiment system for developing and
testing a ranking algorithm: frozen source/checker/configuration, separate
public/private data, strong simple and matched three-call model baselines,
1/2/4/8-check curves, project-cluster analysis, resumable requests and an explicit
advantage gate. Replace one isolated Python policy file to compare a new method.
Run `python3 -m rtl_agent.comparison_lab replay-recorded --output results/lab_replay`
without new API calls. See [the runner and final-study workflow](docs/COMPARISON_LAB.md).

Its expanded retrospective synthetic comparison finds a stronger RRF baseline
at **8/10**, versus the prior gated policy's **7/10** at eight checks. The old
three-call raw-model control is missing, so the evaluator refuses an advantage
claim. All existing cases are development data. Final evaluation requires
registered new-project data and keeps unrepairable cases in the denominator.

The new `/ranking` workspace attaches observed failures, original-circuit
dependency ranges and exact edits to every candidate. Three permuted NVIDIA
rankings are accepted only when their top-eight sets are sufficiently stable;
otherwise a fixed circuit-evidence heuristic decides the order.

With the algorithm frozen before using four new modules, a **synthetic,
known-positive-pool** study passes **7/10** cases, compared with raw-model
ranking **5/10**, circuit evidence **6/10**, and random expectation **3.33/10**.
**Smallest-edit ordering also passes 7/10**: superiority over the strongest
simple baseline is not established. All 240 candidates, 16 mutation attempts,
40 calls ($0.678128 estimated) and four normal controls remain available.
The separate nine-case historical development study gives **4/9**, tying its
circuit heuristic. See [the complete ranking protocol and limits](docs/EVIDENCE_RANKING.md).

The new `/search` study generates small source edits first and asks NVIDIA only
to rank existing IDs. With the same pool and eight-check cap, static search
passes **3/9** known defect profiles and NVIDIA-prioritized search **4/9**.
Both reference controls pass unchanged through a common original-source gate.
Nine ranking requests cost an estimated **$0.111220**, excluding local compute.
The extra acceptance changes FIFO B byte order only; it does not establish the
other bank or all operating conditions. This is a known development cohort with
a restricted lexical grammar, not an SMT solver or novel algorithm. See
[the matched search study and limits](docs/CONSTRAINED_REPAIR_SEARCH.md).

The corrected **V2 known-bug comparison** at `/benchmarks` evaluates nine
historical defect versions and two reference controls. Under the declared,
valid-qualified regression profiles, self-review passed **1/9** and checking
feedback **2/9**. Control traces passed **1/2** and **2/2**, respectively.
All 29 requests (estimated $1.464060), failures and unchanged source/data seals
are retained. A one-case difference does not establish general superiority.

V1's claimed normal-code damage was withdrawn: its TKEEP audit exceeded a
reference implementation's supported input domain. V2 narrows that domain,
masks invalid data, ignores debug output and independently qualifies frame-count
expectations. The original valid popcount improvement must now pass a regression
test. See [the V2 protocol](docs/KNOWN_BUG_BENCHMARK_V2.md). Older studies remain
separate; this golden-trace comparison is not a reference-free behavioral proof.

The new **external UART case** at `/uart` reproduces a historical ZipCPU
flow-control bug from another author and project. The exact fourth NVIDIA
proposal passes 12 serial/flow simulations and two bounded CTS properties after
an indentation-only controller parser fix. All four requests, the first wrong
`keep`, response failures, initial parser rejection and post-hoc recheck remain
visible. Estimated model cost: $0.174519. Scoring uses no corrected RTL.
See [the external case, GPL provenance and limits](docs/EXTERNAL_UART.md).

The new **synthetic property challenge** at `/mutation` repairs intentionally
injected queue faults without using a corrected RTL implementation as its scoring
oracle. NVIDIA accepted repairs for 6/6 injected cases in a frozen 11-request run;
one of two healthy controls received an unnecessary repair decision. Independent
Python deque checks, public properties and same-input Icarus replays are recorded.
See [the synthetic experiment and its limits](docs/MUTATION_CHALLENGE.md).
These results are separate from the historical case comparison below.

The focused hackathon app is now `python3 -m streamlit run rtl_app.py`:
**editable RTL → independent checks → exact source/evidence export**, with three
real historical sequential bugs and a completed 9-pair NVIDIA comparison.
[Deployment](docs/DEPLOYMENT.md), [the full comparison and limits](docs/SEQUENTIAL_COMPARISON.md),
and [the contract audit](docs/RTL_CONTRACT_AUDIT.md) describe the supported scope.
The older `app.py` retains the preceding experiments.

The product is a **web RTL verification and repair workspace**. No physical FPGA
connection is required. The [current RTL direction and evidence limits](docs/RTL_AWARD_PLAN.md)
are fixed around real RTL failures, independent checks, and honest attribution.

The new `/reset` case reproduces a historical verilog-axis asynchronous FIFO bug.
A fresh NVIDIA Nemotron Ultra reasoning request proposed a checked local repair.
The candidate passes three clock/occupancy regressions and a 16-step bounded
reference comparison. Original sources, MIT notices, all earlier failed proposals,
and the exact scope remain in `demo/fifo_reset`.

The `/keep` case adds a real AXI width-adapter bug: disabling source TKEEP
incorrectly produces zero valid output bytes. An actual NVIDIA proposal fixes
only the same-width path and passes 4/6 regressions, so it is **rejected**.
Five paid development attempts, the incomplete proposals, and the independent
maintainer-fix controls (6 regressions and four 20-step comparisons) are retained
in `demo/adapter_keep`. No NVIDIA repair was accepted for this second case.

The official deadline is **2026-10-31 02:00 Korea time**; see the
[verified deadline and internal schedule](docs/SUBMISSION_SCHEDULE.md).

Install `python3 -m pip install -e '.[ui,dev]'` and run `python3 -m streamlit run app.py`.
Numerical-specification and booking prototypes are archived at `/numeric` and
`/booking`; they are not the RTL competition product.

## Arithmetic RTL review and optimization

RTLRefine helps RTL developers decide which AI-generated arithmetic changes to
keep. Paste or upload a change, reproduce arithmetic errors, compare a fixed
library mapping, and export the recommended source with its verification evidence.

The **Review workspace** accepts a change only after all correctness checks pass
and its Nangate45 research-library cell-area estimate decreases. A concrete SAT
counterexample is independently replayed through Icarus and Python before it is
shown. The **Experiment lab** preserves the original generic-cell search and its
completed 108-call NVIDIA comparison without changing those historical results.

See [the original review workflow and its limits](docs/REVIEW_WORKSPACE.md).
That workspace supports the three arithmetic contracts below. The external
workspace adds the three NVDLA instances described next; arbitrary RTL projects
remain outside the current scope. Sequential support is limited to the pinned
FIFO-reset and AXI byte-validity cases described above.

The new [external RTL workspace](docs/EXTERNAL_RTL.md) at `/external` adds three
original, commit-pinned NVDLA modules and a [verified sticky-shift compiler](docs/STICKY_SHIFT_SEARCH.md).
The supplied transform reduces the bidirectional-shift example's Xilinx synthesis
LUT count from **700 to 504**, with every output bit formally checked against the
upstream contract. NVIDIA proposes bounded architecture plans; it did not discover
the transform and did not improve on its default in the small planning pilot.
FPGA counts and library areas are synthesis estimates, without timing or board
measurements. Original sources and their separate license are retained in
[third-party notices](THIRD_PARTY_NOTICES.md).

```bash
python3 -m pip install 'streamlit==1.51.0'
python3 -m streamlit run app.py
```

Open http://localhost:8501 to browse executed review examples without an API key
or EDA tools. Live verification and new NVIDIA proposals require the tools and
isolated workers described below. No model call is made by browsing examples.

The verification pipeline, three benchmarks, persistent budget guard, paired
experiment runner, and local Streamlit demo are implemented. A completed
108-call experiment uses NVIDIA Nemotron 3 Super on Nebius Token Factory.
All candidate sources, validation decisions, and estimated API costs are saved.

<!-- LIVE_RESULTS_START -->
## Measured NVIDIA results

NVIDIA Nemotron 3 Super on Nebius Token Factory, 3 paired trials per benchmark and
6 generation calls per strategy. The comparison completed
**108 calls** for an estimated **$0.6170** using recorded token usage and public rates.

These are model-generated proposals. Every trial, failure, and zero improvement is retained.

| Benchmark | Baseline generic cells | Independent: mean best reduction | Feedback: mean best reduction |
|---|---:|---:|---:|
| Signed INT8 adder tree | 137 | 0.00% | 0.00% |
| INT8 saturation | 39 | 58.97% | 50.43% |
| FP4 E2M1 product | 142 | 19.72% | 17.37% |

Equal call counts do not imply equal token costs. These small repeated trials do not establish
general model performance or that feedback is always better. Full trial ranges, validation
pass rates, costs, and original run records are in [the evidence set](demo/evidence).
Representative UI examples are selected near the median, not by the largest improvement.

![Every paired trial and inference-cost tradeoff](demo/evidence/figures/paired_comparison.png)

A separate Nangate45 mapping measures the generic-cell-selected designs:

| Benchmark | Strategy | Measured trials | Mean mapped-area reduction |
|---|---|---:|---:|
| Signed INT8 adder tree | independent | 3 | 0.00% |
| Signed INT8 adder tree | feedback | 3 | 0.00% |
| INT8 saturation | independent | 3 | -9.52% |
| INT8 saturation | feedback | 3 | -6.35% |
| FP4 E2M1 product | independent | 3 | -2.97% |
| FP4 E2M1 product | feedback | 3 | 1.15% |

These are **non-manufacturable research-library synthesis estimates**, not post-layout
physical area. Timing, frequency and power remain unmeasured. Mapping does not change
the search objective or retroactively select a different candidate.

<!-- LIVE_RESULTS_END -->

## Measured calibration results

| Benchmark | Baseline cells | Calibration cells | Reduction | Simulation coverage |
|---|---:|---:|---:|---|
| Signed INT8 adder tree | 137 | 137 | 0% | 6,497 boundary/random vectors |
| Fixed shift and INT8 saturation | 39 | 16 | 58.97% | All 65,536 inputs |
| FP4 E2M1 scaled-integer product | 142 | 71 | 50% | All 256 input pairs |

These are actual local measurements of developer-authored fixtures. They
establish optimization headroom, and do not demonstrate AI-model performance.
Every valid fixture also passes Yosys equivalence of every output bit. Both
baseline and candidate receive the same ordinary synthesis optimization.
Baselines use balanced addition, shift/clamp, and magnitude-decode/multiply;
no redundant baseline logic was added to inflate reductions.

The adder fixtures include an overflow bug rejected by simulation and a sparse
intentional error that passes simulation but leaves one output bit unproven.
An equivalent rewrite with an unchanged count is also retained in the history
and rejected as an improvement.

Recorded evidence is in [demo/runs](demo/runs). The UI labels it as recorded,
developer-authored validation. Generic cells are not physical area, frequency,
latency, or power. Those quantities remain unmeasured.

## Quick start

Use Python 3.11 or later from this repository root. The CLI uses the Python
standard library. External Linux tools are Yosys, Icarus Verilog, Verilator,
bubblewrap, and util-linux prlimit.

```bash
sudo apt-get install yosys iverilog verilator bubblewrap util-linux
python3 -m rtl_agent.cli doctor
```

The recorded calibration uses Python 3.13.9, Yosys 0.51 and Icarus 11.0.
The optional environment.yml pins those tool packages for Conda reproduction;
Verilator can still be installed locally with the helper below.
Those runs record Icarus as their syntax/lint fallback because Verilator was
not installed then. Live optimization requires Verilator. Filename and unused
signal style warnings are excluded; width and other lint checks remain enabled.
Every evaluation records its actual tool versions and trusted script hashes.
Distribution versions can produce different counts.

Without sudo on Debian/Ubuntu, install only Verilator into this project:

```bash
python3 scripts/install_verilator_local.py
```

This downloads the host repository package and unpacks it under .tools without
changing system packages or Python environments. RTLRefine discovers the local
wrapper automatically and mounts its tool directory read-only in the worker.

For RTL you authored and reviewed yourself:

```bash
python3 -m rtl_agent.cli baseline --benchmark requantize --trusted-local
python3 -m rtl_agent.cli evaluate --benchmark fp4_product --candidate tests/fixtures/fp4_factorized.v --trusted-local
```

The trusted-local option disables OS isolation and records that fact. It is
not available on the live optimizer. Source filtering and resource limits do
not replace OS isolation. Without this option, candidate evaluation requires
a working bubblewrap sandbox, with no automatic fallback that disables it.
Workers have no provider credentials and use fixed argument lists, resource
limits, a private filesystem view, and a separate network namespace.

Rebuild all built-in, developer-authored fixtures into a new directory:

```bash
python3 -m rtl_agent.cli build-demo --trusted-local --output results/calibration
```

This command makes no model requests. Existing run directories are never
overwritten. Input specifications and independent arithmetic models are in
[benchmarks](benchmarks).

## Local demo

```bash
python3 -m pip install 'streamlit==1.51.0'
python3 -m streamlit run app.py
```

Open http://localhost:8501. The default Review workspace explains concrete
rejections and accepts pasted or uploaded changes matching a built-in contract.
Choose Experiment lab (or `/lab`) to select a benchmark and inspect decisions, source
diffs, proof coverage, simulation evidence, and tool logs. Export a standalone
HTML report, CSV table, run metadata, or the best valid RTL. The default server
binds to loopback; a public demo has not been deployed.

Recorded developer fixtures and live NVIDIA execution have explicit provenance
labels. The live action is disabled until the host has the necessary tools,
local credentials, and isolation. Readiness checks do not authenticate the
provider. Uploads must match a selected fixed contract; a browser API-key field
is not provided. New review recommendations use mapped cell area, while the
preserved experiment still uses its original generic-cell objective.

## Connect NVIDIA on Nebius

If you do not already have a local .env containing your key, create it from
[.env.example](.env.example). Preserve an existing configured file.

```bash
cp .env.example .env
```

Set NEBIUS_API_KEY locally. The controller uses the
[documented Nebius endpoint](https://docs.tokenfactory.nebius.com/quickstart).
It redacts the key from persisted provider responses, excludes credentials
from worker environments, and prints only key-presence booleans in doctor.

On a host with network access:

```bash
python3 -m rtl_agent.cli models
python3 -m rtl_agent.cli setup-model
python3 -m rtl_agent.cli probe-model --thinking off --json-mode
```

The model list comes from the actual account. Setup prefers an available,
priced Nemotron 3 Super, then Nemotron 3.5 Lightning, and saves the chosen ID
atomically while preserving the key. An explicit --model also requires
account availability and a configured official price. No model availability
is assumed from its name.

The probe makes one real, budgeted request with at most 1,024 output tokens
and executes no RTL. Response receipt alone is not an optimization result.
DNS or connection errors do not validate or invalidate the key.

When doctor confirms execution prerequisites, start with a small pilot:

```bash
python3 -m rtl_agent.cli optimize --benchmark fp4_product --strategy feedback --max-iterations 3
```

The model may return only verilog and rationale fields in one JSON object.
It cannot alter the baseline, mathematical specification, golden model,
testbench, or scripts. Feedback includes the previous candidate, rejection
reason, and a bounded tool-log excerpt. The best valid design is preserved
through failures and budget stops.

## Persistent inference budget

[Budget policy](configs/budget.json) allocates a total $50: $20 development,
$20 judging, and an unallocated $10 safety buffer. Development is the default
phase. A later switch to judging retains the same cumulative ledger.

```bash
python3 -m rtl_agent.cli budget
```

Every generation, including a probe, reserves a conservative maximum before
an HTTP request. This uses the entire documented input-context bound plus the
output-token limit, even for a short prompt. Reported usage replaces that
reservation with a cost estimate. Missing or inconsistent usage, transport
errors, and controller crashes retain the reservation. File locking prevents
concurrent requests from racing past the allocation.

Unpriced models and unreadable spend history fail before inference. The
ledger is .state/spend.json, excluded from Git. Retain it across restarts and
deployments; deleting it loses spend history. No automatic retry or refund
hides an unknown request outcome.

[Pricing](configs/pricing.json) records official public rates checked on
October 21, 2026. Estimates are not account-billing data or a provider-side
spending cap. Confirm applicable account prices and retain the buffer.
Hosting and calls outside this client are not included.

Per-run request, completion-token, observed total-token, source-size, tool-time,
and wall-time bounds are in [default configuration](configs/default.json).
The observed token threshold can be crossed by its final response; pre-request
USD reservations provide a separate check.

## Measure the effect of feedback

Independent sampling always sees the baseline. Feedback search sees the best
valid candidate and the previous attempt's results. Both receive the same
number of generation calls, preserve their best valid design, and use identical
evaluation conditions. Strategy order alternates across repeated trials.

Inspect a plan without making API requests:

```bash
python3 -m rtl_agent.cli experiment-plan --benchmark all --trials 3 --requests 6
```

That plan contains 108 generation calls if completed. Start with one paired
trial on one benchmark:

```bash
python3 -m rtl_agent.cli experiment --benchmark fp4_product --trials 1 --requests 3
```

Results include experiment.json, comparison.json, comparison.csv, and every
original run. Summaries report validity rate, best generic-cell reduction,
cost estimates, and elapsed time. Equal call counts do not imply equal token
costs. A first-candidate result is a one-shot reference, not an equal-budget
competitor to a multi-call strategy.

Only completed pairs with matching model IDs, baseline hashes, immutable
assets, tools and limits enter group summaries. Incomplete and ineligible
runs remain visible with exclusion reasons. Developer-fixture records cannot
enter model comparisons. Completed live comparison records are retained in the evidence set.

## Verification scope and artifacts

Supported RTL is stateless and combinational, using continuous assignments.
Parameters, procedural state, directives, attributes, unknown/high-impedance
literals, external files and system tasks are excluded. Specs fix port names,
widths, signedness, bit order, rounding, and saturation.

Simulation compares observed outputs with independent Python arithmetic.
Equivalence uses equiv_make, equiv_simple -undef, and equiv_status -assert.
The checker requires one comparison per output bit and explicit all-proven
counters. Empty proofs are errors. Failed proofs without a demonstrated
counterexample remain UNPROVEN.

Candidate statuses are PASS, FAIL, UNPROVEN, TIMEOUT, and ERROR. Unreached
stages are NOT_RUN. Only all-pass candidates can be measured and accepted;
acceptance also checks matching evaluation assets and tool versions.
Failed candidates and zero or missing baseline counts have no improvement
percentage. Mapped physical area, delay, and power remain null.

The FP4 benchmark is an exact scaled-integer E2M1 product, with no block scale
or accumulation. It is not a complete NVFP4 MAC. The saturation block uses one
fixed shift and does not implement general quantization.

Runs under results/ include run.json, results.csv and report.html. Candidate
folders retain RTL, trusted asset snapshots and hashes, configuration, command
records, logs, simulation observations, proof artifacts, and synthesis stats.
Live requests retain redacted provider responses, usage and cost metadata.

```bash
python3 -m rtl_agent.cli report --run-dir results/<run-directory>
python3 -m pytest -q
```

Tests use real EDA on developer-authored fixtures and Streamlit AppTest for the
UI. Provider-boundary and orchestration tests use clearly labeled fake provider
data in temporary directories, never exposed as production inference or demo
performance claims.

The completed real-model trials and paired comparisons are included in the
evidence set. Before submission, provide judging access and publish the source
with this [MIT license](LICENSE) and an English demo video. The hosted demo,
public repository, YouTube upload, and Devpost entry have not been published.

## Further documentation

- [Add a trusted benchmark](docs/ADDING_BENCHMARKS.md)
- [Recorded inference controls and development observations](docs/INFERENCE_NOTES.md)
- [Optional research-library mapped-area estimates](docs/MAPPED_AREA.md)
