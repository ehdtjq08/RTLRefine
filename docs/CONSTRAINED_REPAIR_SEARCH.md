# Constrained repair search: static order versus NVIDIA ranking

This is a new development ablation, separate from the two-call V2 study.
It uses the same nine qualified historical defect scenarios and two reference
controls, with the unchanged V2 input domains, valid-output masks and oracles.
The grammar was developed after inspecting V2 failures and one retention pilot.
These are known development cases, not held-out generalization evidence.

## What was actually implemented

The engine generates small source changes before any model request. It uses a
restricted lexical grammar and Yosys-resolved original-source signal widths;
it is neither a general Verilog AST engine nor an SMT solver. The finite edit
families cover persistent defaults, missing reset assignments, reported-value
clearing, reset-qualified readiness, nearby scalar guards, matrix index strides,
cycle-qualified acknowledgment delay and 32-bit word byte reversal.

Candidate generation reads the original input and its read-only dependencies.
It never reads a corrected target implementation or test result. Policy-invalid
candidates are filtered statically; no candidate simulation is used to construct
the pool. There are 400 retained candidates across the eleven contexts, with
28–47 per context. Pools, generation code, controller code and V2 data are sealed
before ranking. All seals matched afterward.

NVIDIA Nemotron Ultra through Nebius Token Factory receives the original code,
public role, original-source discovery mismatch and the pre-generated candidate
menu. It returns only existing IDs and a rationale. It cannot write RTL, create
new candidates, expand the pool, change parameters or read audit observations.
All nine required rankings parsed successfully; there were no fallback rankings.

## Matched comparison

Both methods receive exactly the same pool and a cap of **eight edited candidate
checks per case**. They share a source-order prefix of two candidates. Static
search continues in deterministic round-robin family/source order. The guided
method uses the NVIDIA ordering after that prefix; omitted IDs retain static
order. Ranking happens before any candidate is simulated. The model settings
are thinking disabled, temperature 1.0, top-p 0.95, maximum 4,096 output tokens.
The local ranking estimate cap is $3 within the unchanged persistent budget.

An original source that passes discovery is kept by both methods without model
inference or edits. This is a common execution gate, not model recognition of
healthy code. Otherwise each method stops on its first discovery pass. BOTH
selections are fixed before either selected source is audited. A failed passive
audit never grants another candidate or changes ranking. No audit result is fed
to NVIDIA.

The methods share a native evaluation cache. Physical checks are counted once,
and logical checks/tool cost are attributed to each method. Cached measurements
are not independent end-to-end speedup measurements. Ranking has additional API
cost and latency; local compute is not included in the dollar estimate.

## Executed outcome

| Method | Real trace passes | Reference-control passes | Logical candidate checks |
| --- | ---: | ---: | ---: |
| Static search | 3/9 | 2/2 | 49 |
| NVIDIA-prioritized search | 4/9 | 2/2 | 46 |

Both passed three real cases, only the guided order passed one, and both failed
five. There were 65 unique edited-source native evaluations. Four candidates
failed compilation; these remain charged against the search budget and recorded.
The grammar does not guarantee elaboration validity. Nine actual ranking calls
cost an estimated **$0.111220**, all settled. Summed planning wall time was
30.5371 seconds. Logical discovery tool time was 111.9673 and 103.2893 seconds;
these figures exclude common original/audit work and do not establish speedup.

The extra guided acceptance is the SPI byte-order scenario. NVIDIA placed a
byte-reversal option inside the eight-check budget; static search did not reach
it. The selected patch changes **FIFO B only** and passes all three 522,559-cycle
profiles. These traces have not established the FIFO A path or full operating
space. It is a scoped trace pass, not a claim of a complete all-bank repair.

A partial frame-FIFO reset candidate passed the 17-cycle public discovery test
but failed both 136-cycle extra audits. Both methods stopped and rejected it,
even though a more complete reset candidate existed later in the pool and the
model ranked it highly. This exposes the limitation of a greedy public gate;
using private audits to select that later candidate would invalidate the study.

The one-case difference in this small, tuned development cohort does not prove
general or statistical superiority. The older V2 1/9 versus 2/9 code-generation
study had a different compute budget and must not be called a matched speed or
accuracy baseline for this search study. Earlier results are not pooled.

## Prior work and next scope

Finite/symbolic RTL repair and LLM-guided symbolic repair already exist:
[RTL-Repair](https://dl.acm.org/doi/10.1145/3620666.3651346) and
[Clover](https://arxiv.org/html/2604.17288). No first-algorithm or paper-novelty
claim is made for combining those ideas here. Typed AST generation, broader
public discovery tests, model-free ordering baselines and a separate unseen
cohort would be necessary before stronger claims.

The `/search` page displays every result, actual ranking, tested order, selected
source and patch. Selected sources can be rechecked against the same profiles
without model calls. Downloads retain raw plans, all failures, candidate pools,
controller source, exact inputs/expected values, MIT/GPL source licensing and BSD
artifact attribution. Native execution remains under the existing bubblewrap
limits. Public hosting/repository/YouTube/Devpost publication remains pending.
