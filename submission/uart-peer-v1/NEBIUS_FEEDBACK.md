RTLRefine uses `nvidia/Nemotron-3-Ultra-550b-a55b` on Nebius Token Factory for
structured RTL edits. The model sees permitted source, public testbenches and
actual public execution failures. Final additional profiles are withheld until
selection is fixed. Native verification does not depend on model diagnoses.

The new UART development used six actual requests across three runs. The first
two no-thinking responses repeated an incorrect bit-order diagnosis and failed
the public test. In the next run a broad edit failed compilation, then the
reasoning-enabled revision reached its 6,144-token cap without a complete patch.
I kept each response and rejected every incomplete or failing export.

I changed the generic revision context so the latest failure follows the old
proposal, explicitly labeling the old diagnosis as rejected. A later run used a
6,144-token fast proposal and a reasoning-enabled revision capped at 12,288 tokens.
The fast proposal failed; the revision changed both vendor files and passed all
eight fixed profiles, followed by the exact exported standalone checker. No final
audit feedback was used to revise a patch.

The six-request application estimate is $0.085415 under the recorded rates;
the successful last run alone is $0.027018. These are not an account invoice.
Prompts, caps and stochastic outputs changed during exposed development, so
these observations do not establish general model superiority or unseen accuracy.
The known historical sources could have appeared in training data.

Strict JSON schemas help parsing but do not ensure correct HDL semantics,
line ranges or compilation. Native logs, finish reasons, raw usage and complete
failure records are essential. Repeated wrong proposals and truncated reasoning
need explicit treatment rather than an accepted-looking partial response.

Useful platform additions would be separate, documented reasoning and final
answer budget controls; clearer schema/truncation diagnostics; and usage receipts
that reconcile directly with application reservations. The existing application
keeps its persistent total/development caps, a two-request repair limit and no
automatic retry after ambiguous network completion.

The earlier AXI request and FIFO development records are retained separately.
Packaging and executing the exported CI uses no new inference. Actual model
results in the video are labeled as recorded; native checks run fresh.
