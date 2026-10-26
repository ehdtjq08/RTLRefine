RTLRefine uses `nvidia/Nemotron-3-Ultra-550b-a55b` through the OpenAI-compatible
Nebius Token Factory API to diagnose RTL failures and propose structured repairs.
Each repair action permits at most two bounded requests. Original source,
declared design dependencies and public checks provide context; audit benches
are excluded. Native workers receive no API credentials.

Token usage and finish reasons were useful for cost accounting and for rejecting
incomplete responses. In an early run, a 19,659-token prompt and a 12,288-token
output cap produced 12,064 reasoning tokens and `finish_reason=length`. The
structured answer was incomplete. Its recorded estimated cost was $0.056523.

For the bounded example workflow, a compact 6,960-token prompt with thinking
disabled later returned a valid 418-token answer at an estimated $0.008214. These
are development observations under recorded rates, not a controlled model
comparison. The user-project path uses a separate 6,144-output-token cap and
structured original-line edits.

The model sometimes supplied a plausible but incorrect causal explanation.
RTLRefine displays that explanation as an unverified hypothesis. Independent
compilation and the supplied testbenches determine whether a patch is accepted.

I would find three additions useful: an explicit reasoning-token budget within
the total output limit, clearer diagnostics when structured output is truncated,
and a provider usage receipt that can be reconciled with application-side cost
reservations. The current application retains uncertain reservations and never
automatically repeats an ambiguous request.

Raw responses, inference settings, rejected attempts and exact source hashes
are retained so these observations can be checked against executed runs.
