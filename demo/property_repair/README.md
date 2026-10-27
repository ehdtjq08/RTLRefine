# Independent FIFO property repair

The examples are authored integration fixtures, not historical bug discoveries.
`summary.json` describes the cohort. Each run preserves its original source,
native logs, property monitor, counterexample, independent replay, inference
response when used, and exact selected source/archive hashes.

`development_failures/` keeps native trials that timed out, including 28-state
checks. They are UNPROVEN and are not counted as passing results. The current
defaults are 12-state discovery and final bounds 16 and 20. The protocol and
supported FIFO contract are in `docs/PROPERTY_REPAIR*.md`.

No corrected reference FIFO RTL is loaded by the verifier. Native checks and
inspection of recorded model responses make no new inference requests.
