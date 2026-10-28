RTLRefine uses `nvidia/Nemotron-3-Ultra-550b-a55b` on Nebius Token Factory for
structured edits to permitted RTL files. Public contract failures, input traces
and actual compiler diagnostics guide at most two requests per repair. Final
audit source, results and depths remain outside the model context.

The first v1.4 development run returned two broad line edits that failed public
compilation; neither produced an accepted export. The second proposal repeated
the first because detailed syntax diagnostics had not reached revision feedback.
I retained both responses, routed those diagnostics explicitly and clarified how
current registered state drives current handshakes. A separate follow-up request
produced a patch that passed all fixed checks and standalone regressions.

These three development requests cost an application-estimated $0.014607 under
the recorded rates, not an account invoice. The successful follow-up request was
$0.004597. The examples are exposed development fixtures, not a controlled model
comparison or unseen repair accuracy. No final audit was used to revise a patch.

Structured output made edits easier to parse, but semantic and syntax errors
still required executable checking. I label model diagnoses as hypotheses.
Token usage and finish reasons helped preserve incomplete/uncertain requests in
the accounting record without automatically repeating an ambiguous HTTP request.

Useful platform additions would be clearer truncated-schema diagnostics,
separate reasoning-token budget controls and usage receipts that can be reconciled
with application-side reservations. Native checking time is recorded separately
from inference cost; resource estimates are not physical timing or power results.
