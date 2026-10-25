# Known-bug study V2: input-domain and output-validity correction

V2 supersedes the development V1 interpretation. All V1 raw model responses,
frozen records and source archive remain preserved. They are not pooled with V2.

## Why the first interpretation was withdrawn

The V1 audit generated arbitrary TKEEP bitmasks for a frame-length monitor whose
research-reference implementation counts only masks of the form `2^k-1`.
Its NVIDIA reference-control rewrite used popcount, which correctly handles
more masks. Rejecting that change as a damaged design was wrong: the oracle and
the broad stated input role disagreed. The V1 video must not be used as the
submission video, and its normal-code-damage claim is withdrawn.

V2 defines the selected reference-supported domain explicitly: contiguous
low-order keep bits, including zero. This restriction applies to this artifact
profile; it is not claimed as a general protocol requirement. A new independent
Python transaction/count model checks expected valid pulses and reported lengths
before any model call. A test also feeds the exact V1 popcount source to V2 and
requires it to pass. No source change alone is described as harmful.

## Pre-inference corrections

- Frame-length audit masks stay in the reference-supported domain. Held source
  values remain stable under stalls, and synchronous resets are modeled explicitly.
- Stream payload/sideband values are compared only when expected valid is set.
  Frame length is compared only when its valid pulse is set. Wishbone data is
  compared only when expected acknowledgment is asserted.
- SPI debug output is not a behavioral oracle. SPI audit transformations change
  FIFO payload bytes, preserving command/configuration words and public timing.
- The cohort is requalified and independently sealed before V2 inference.
  No V1 response is silently reused as a new paid request or relabeled as V2.

All nine historical scenarios still reproduce after masking invalid/debug
observations. Research corrected controls and two reference-control inputs pass.
The same licensed artifact revision is used:
`ekiwi/rtl-repair@71e1afc0b9a2327d008b46acd415cf3f0343a938`.
These are research-adapted historical versions, not untouched upstream copies,
new discoveries or an unseen benchmark. Some families were used in development.

## Paired protocol

V2 has nine defect cases and two reference controls, one trial per case.
NVIDIA Nemotron Ultra runs on Nebius Token Factory, thinking enabled,
temperature 1.0, top-p 0.95, maximum 24,576 output tokens. The methods share the
first proposal, then use at most one self-review continuation or one continuation
with discovery execution feedback. Each method has a cap of two logical calls.
Branch order alternates; at most two independent case contexts run concurrently.

If discovery passes, both methods stop even if an audit fails. Audit observations
do not enter model context or grant another request. Labels and corrected code
are absent from the prompts. Original line-range edits are applied mechanically,
with a declared final newline added to replacement blocks if missing. There is
no functional manual repair. The estimated run cap is $5 within the persistent
$50 total / $20 development guard; prior V1 spend remains in that same ledger.

The primary measure is **trace acceptance under the declared profile**, not
unbounded correctness or general semantic repair accuracy. The oracle still uses
published/corrected-control golden traces, with an independent frame-count guard
for that family. Cycle-exact readiness/timing can reject other legal architectures.
Source-policy rejections are not proof of semantic incorrectness. Native Verilator
4.038 uses zero unspecified initialization and retained explicit initializers.
All code runs in the existing resource-limited bubblewrap boundary.

## Records and UI

`external_cases/known_bugs_v2/FROZEN.json` pins every source, trace, expected value
and checker before V2 calls. The complete result is exported separately to
`demo/known_bug_comparison_v2`. `/benchmarks` shows the V2 metrics, all failures,
reference-control source edits and the oracle-revision explanation. Its editable
workspace uses the same sealed profiles. Browsing and native checks cost no API
request; optional live repair is explicit and separately budgeted.

No small-cohort difference is described as statistical/general superiority or
human productivity gains. No study is pooled with the authored synthetic queue,
the earlier negative three-case comparison or the external UART development run.
MIT/GPL source notices, licenses and corresponding source are retained.

## Executed V2 outcome

The complete separately frozen run used 29 actual requests, estimated $1.464060,
all settled. Each arm had 20 logical calls including its shared-first attribution.
Self-review passed the declared traces in 1/9 real cases; checking feedback in
2/9. Both passed one case, feedback alone one, and both failed seven. Reference
control traces passed 1/2 for self-review and 2/2 for feedback. Source-token edits
were 2 and 1 respectively; an edit is not automatically called damage.

All source/checker/data seals matched after inference. The difference is one
case in a small, selected one-trial cohort and does not establish general or
statistical superiority. All failures and the withdrawn V1 interpretation remain
available. Public publication and a human usability study remain pending.
