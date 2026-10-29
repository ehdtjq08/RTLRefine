# Historical UART pair versus independent serial peers

The selected MIT-licensed source is the unmodified parent of upstream change
`db0017a22c57731d69a4a2844bc1e4f3f36abd10`, which changes both transmitter and
receiver from MSB-first to LSB-first ordering. This is a known historical behavior
change evaluated against an explicit LSB-first peer contract, not a new discovery
or a regression introduced after a prior correct revision. Public source may
have appeared in training data. The assistant inspected upstream history during
qualification; this is an exposed development case, not a blinded benchmark.

The original pair can exchange bytes with itself: the wrong ordering cancels
in TX/RX loopback. Separate peers are therefore used for admission. TX samples
each serial bit cell against the offered parallel word's least-significant bit
first. RX receives independently generated serial bits and must publish the
original parallel word. Neither direction uses corrected RTL as an oracle.

The three-file project contains untouched vendor TX/RX leaves and a disclosed
stateless read-only packaging adapter. Only the two vendor leaves may be edited.
The adapter exposes separate serial TX and RX pins and both parallel interfaces;
it never reverses data or connects TX to RX internally. Testbench-only loopback
is a deliberately weaker smoke control, clearly distinct from peer admission.

The normal project contains one public profile and seven audit profiles. All
share the declared protocol monitor; the additional parameter/seed profiles are
withheld from model context. They cover 5/6/7/8-bit words, 8/16/24/32/40 clocks per
bit, asymmetric patterns and deterministic pseudo-random words. Two profiles also
check pending RX stability without a new incoming word, explicit overrun/newest
replacement behavior, invalid stop-bit rejection and reset during traffic.
There is no parity or physical CDC/metastability claim.

Before any model call, the original loopback-only control must pass, the original
peer project must fail, the maintainer source must pass all eight profiles, and
TX-only/RX-only partial corrections must fail. Input bytes and the generator are
sealed in qualification.json. The initial qualification's testbench used the
reserved SystemVerilog identifier `before` and did not compile. That failed
record is retained; renaming the bench-local variable occurred before inference.
The v2 qualification passes. No vendor source or acceptance evaluator was changed.

Repair uses the ordinary project controller, its fixed native checker and at
most two actual NVIDIA requests. The public original failure may guide a patch;
final audit failure is terminal. An accepted export must additionally pass its
exact standalone CI runner. Checks remain finite simulation at stated profiles,
not unbounded UART correctness, unseen accuracy or a general algorithm advantage.
