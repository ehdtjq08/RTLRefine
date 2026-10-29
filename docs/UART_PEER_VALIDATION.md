# UART verification beyond a self-consistent loopback

Open `/external-validation`, then **UART serial peers**. The page displays actual
sampled bits and decoded bytes, the two-file NVIDIA patch, all six development
requests and native replay buttons. It makes no inference request.

The MIT-licensed `alexforencich/verilog-uart` original pair is pinned at
[`62eb6f5d45b6`](https://github.com/alexforencich/verilog-uart/tree/62eb6f5d45b62be3029308da58c64bafbdb3aac6/rtl).
Upstream changed both directions to LSB-first at
[`db0017a22c57`](https://github.com/alexforencich/verilog-uart/commit/db0017a22c57731d69a4a2844bc1e4f3f36abd10).
This is a known historical behavior change against an explicit peer contract,
not a newly discovered defect or an introduced regression. This author also
wrote verilog-axis; it is not an additional independent-author sample.

## Observed behavior

The original pair passes its three-frame loopback smoke (678 evaluations). But
an independent LSB-first peer sees `0x01 → 0x80`, `0x80 → 0x01`, and `0x96 → 0x69`
in **both** directions. TX-only and RX-only maintainer corrections are rejected.
The UI's cells come from actual bit-center samples; they are not a complete
continuous waveform. The checker additionally evaluates every tested bit cell.

The selected NVIDIA correction changes both vendor files and passes eight
profiles / 186,772 assertion evaluations, followed by the exact standalone CI
runner. Expected bits come from offered bytes, expected received bytes from the
independent serial stimulus. No corrected RTL is loaded as an oracle. The
read-only stateless adapter exposes both leaves without reversing or looping
signals. Original vendor headers, full MIT license and byte hashes are retained.

Profiles cover 5–8 data bits, five baud divisors, deterministic patterns/seeds,
pending RX output, overrun, invalid stops and reset during traffic. Public and
audit benches share the declared protocol monitor; the seven additional profile
settings are withheld. There is no parity, physical timing or CDC guarantee.

## Development evidence and controller change

All six actual requests remain in `demo/uart_peer/development`. Two runs failed:
the first repeated a wrong diagnosis, and the second reasoning revision hit its
6,144-token cap after a fast proposal failed compilation. A third run used the
same sealed tests; its fast proposal failed and reasoning revision passed with
a 12,288-token completion cap. The six-request application estimate is $0.085415.
The successful last run alone cost $0.027018. No final audit result guided a retry.

The generic agent now labels previous proposals as rejected hypotheses and ends
revision context with the latest public execution evidence. The first proposal
uses no thinking / at most 6,144 completion tokens. A revision with a prior
proposal enables reasoning / at most 12,288 tokens. Each repair still permits
at most two requests; budget reservations, the $4 per-request reservation guard,
persistent $50/$20 caps and ambiguous-request no-retry policy remain active.

The native checker and sealed test inputs did not change. The initial
pre-inference bench syntax failure is disclosed separately. Earlier failed
model/controller snapshots are preserved. Because prompts, token limits and
stochastic responses changed during exposed development, this is not evidence
that reasoning or feedback generally outperforms another strategy. Training
contamination cannot be excluded. Matching maintainer source hashes is a
post-hoc observation, not the acceptance criterion.

## Reproduction

```sh
python3 scripts/validate_external_uart_bitorder.py qualify --output results/uart-qualification
python3 -I scripts/check_general_project_ci.py --output results/project-ci-cycle
```

The second command uses the checked exports and no app imports or model key.
The UART CI cycle restores **both** original vendor files to reproduce the peer
failure, then restores the checked files for exit codes **0 → 1 → 0**. Changing a
protected audit produces exit 2. The same ZIP works in the ordinary `/project`
route, retaining its standalone suite and protected checks.
