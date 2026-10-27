RTLRefine uses `nvidia/Nemotron-3-Ultra-550b-a55b` through Nebius Token Factory
for structured RTL edits. In the new FIFO workflow, I give it the original
design, immutable public contract and an input sequence whose failure has been
reproduced independently. Audit benches and final audit observations are not
sent to the model.

The initial integration run repaired an authored simultaneous-transfer defect
with one request, followed by four smoke expectations, 65 sequence checks and
bounded property verification. Its application-estimated inference cost was
$0.003004 at the recorded rates. This is one development example, not a model
accuracy or cost benchmark.

Token usage and finish reasons helped distinguish complete answers from failed
generation. An earlier long-reasoning request used 12,064 reasoning tokens within
a 12,288-token output cap and returned incomplete structured output. Compact
context, thinking disabled and typed line edits made this workload more practical.

Plausible explanations were still insufficient to establish a fix. I label
diagnoses as hypotheses and use independent tools to decide acceptance.

Useful additions would include explicit reasoning-token limits within the
overall output cap, clearer structured-output truncation diagnostics, and
provider usage receipts that reconcile with application-side cost reservations.
The application keeps uncertain reservations and does not automatically repeat
an ambiguous request. Native proof time is reported separately from inference.
