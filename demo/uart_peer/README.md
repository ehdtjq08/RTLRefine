# UART loopback and independent peer evidence

The unmodified historical transmitter and receiver pass a closed-loop smoke
test yet reverse asymmetric bytes against an explicit LSB-first peer. This
folder retains original/maintainer/partial-control qualification, every actual
NVIDIA development response and the final checked two-file repair with CI.

- `qualification/`: successful pre-inference qualification with sealed inputs.
- `pre_inference_compile_failure/`: initial bench-local reserved-word error,
  fixed before the first inference. Vendor source and native evaluator unchanged.
- `development/run1`: two rejected no-thinking proposals.
- `development/run2`: rejected fast proposal and truncated reasoning revision.
- `development/run3`: rejected fast proposal, then accepted reasoning revision
  with a separately declared larger completion cap. All eight fixed profiles
  and the exact standalone runner pass.
- `projects/`: original loopback-only, original independent-peer and selected
  NVIDIA/CI ZIPs. Loopback-only PASS has explicitly limited scope.

Six actual development requests cost an application-estimated $0.085415 under
the recorded rates; this is not an account invoice. No final audit feedback was
used to revise a patch. The final source matches the known maintainer source
bytes as a post-hoc observation; that comparison was not the acceptance oracle.

The public/audit benches share the declared protocol monitor; additional
parameter/seed profiles were withheld. This is selected exposed development,
not a blinded benchmark, new discovery, introduced regression, unbounded proof
or general model/algorithm superiority. See `external_cases/uart_bitorder_external/PROTOCOL.md`.

The project's `PROVENANCE.json` describes the imported upstream input. Selected
source changes and hashes are in the run's `result.json`; checked exports are
not a claim that selected source remains byte-identical to the original input.
