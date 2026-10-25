# Frozen NVIDIA paired comparison

The complete cohort is in `demo/sequential_comparison`. It contains **9 pairs**:
three historical public RTL cases, three trials each. Both branches start from
the same first NVIDIA proposal. If it passes, both stop. Otherwise, each branch
gets one further request: independent self-review or checker feedback. Branch
execution order alternates. Both have the same two-call cap, model, settings,
full-source output schema and acceptance gate.

| Branch | Accepted trials | Logical model calls |
| --- | ---: | ---: |
| Self-review | 3 / 9 | 16 |
| Simulation + bounded-input feedback | 2 / 9 | 16 |

Actual unique paid requests: **23**. Reported-token cost estimate: **$0.798303**.
Shared first calls count once in unique spending. Per-arm attributed costs include
that first call and must not be summed to infer the provider bill.

This result does **not** show a feedback advantage. The small development cohort,
public historical code, two previously used development cases, unknown training
familiarity, strict header-preservation policy and bounded/cycle-level oracle
prevent a general model-performance claim. These are acceptance counts under
the frozen rule, not general semantic-repair accuracy. See the contract audit
for reference timing and environment restrictions.

The accepted AXI candidate in self-review passes all six mask/width simulations
and four 20-step comparisons. The third-case initial proposal passes all three
directed simulations but fails the 12-step reference comparison. These examples
illustrate the gate; they do not replace the complete result table.

`aborted_development_pilot` retains two additional paid requests before a Yosys
JSON escape handling error interrupted the first controller. They are excluded
from the completed cohort. Earlier local-edit experiments are also retained in
their original case evidence and are not pooled with this protocol.

No generated RTL is manually repaired before acceptance. Model responses,
prompts, exact source bytes, EDA logs, witnesses, controller snapshots and protocol
hashes are retained. The fixed reference source is excluded from prompts.
Only top-level symbolic inputs are passed back; reference internal states are
filtered. Symbolic traces are not independently replayed. The Icarus witnesses
are separately directed regressions.
