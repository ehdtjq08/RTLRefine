# Current submission: guided RTL repair with fast screening

The homepage is a single supported repair workflow. It reproduces a failure,
generates a finite patch pool from the original source, asks NVIDIA Nemotron on
Nebius to prioritize hypotheses, and checks the selected exact source before
export. A first-choice patch is checked independently as a fast path. If it
fails the public profile, shared candidate compilation screens the remaining
pool. The agent may revise its hypothesis using those public results.

The current UI places source review and captured signal lanes on the left,
with the actual three-profile verdict, source fingerprint and exports on the
right. SVG signal lanes show recorded samples rather than generated waveforms;
unqualified expected values remain marked `?`. Full values and unverified model
prose are available in expanders. A modified editor hides the prior accepted
result, and Restore example restores the pinned input without making a model
request. The visual layer does not change the repair or admission policy.

Selection never sees the two private audits. The selected uninstrumented file
is separately compiled and checked on the public profile and both audits. An
audit failure ends that run without another candidate. A source that already
passes the public profile is also checked on both audits; it is not accepted
from a public pass alone. Model explanations remain unverified hypotheses.

## Actual outcomes retained

- Featured live video run: packet-FIFO overflow, two NVIDIA requests, 43 source
  hypotheses, initial patch rejected, 42 remaining candidates screened, then
  exact candidate_001 admitted after independent checks. Total 19.77 seconds.
- A separate one-request overflow run completed in 9.85 seconds with its first
  candidate accepted; a length-monitor run completed in 10.73 seconds and a
  frame-FIFO reset run in 10.01 seconds. These are curated development examples,
  not an unseen accuracy estimate or fair agent-superiority comparison.
- Earlier overflow development attempts remain available, including the
  12,288-output-token response that ended at its cap and a valid but incorrect
  initial reset hypothesis. No functional source correction is inserted by the
  controller. Candidate code is generated before model ranking.
- The browser test pastes a deliberately incomplete reset patch. It passes the
  public profile but fails both audits; its 1/3 result is rejected and it has no
  accepted-RTL download. Editing source also removes a previous success.

## Compile-once screening mechanism

`rtl_agent/batch_repair/schema.py` combines nonoverlapping source-edit sites
behind a fixed runtime selector. Expression edits become selector-controlled
expressions; supported procedural insertions become guarded blocks. Multi-site
patches use the same selector at every site. For an edited child module, trusted
instrumentation references the selector on its top-level wrapper.

Each candidate starts in a separate native process with the selector set before
the first evaluation. This avoids carrying state from another candidate. The
inactive selector's complete public output stream must equal an ordinary build
of the original source. Elaboration-only changes and unsupported statement edits
take the standalone path. If a batch cannot compile or its inactive control
mismatches, the complete pool falls back to independent builds. A batch result
is never sufficient for final admission.

The paired timing protocol was written before timing collection. It fixes three
cases, compares identical complete pools, uses fresh build directories, alternates
which arm runs first, includes controls/fallbacks, and retains all results:

| Profile | Candidates | Serial s | Shared s | Ratio |
|---|---:|---:|---:|---:|
| Frame length | 28 | 52.433 | 4.349 | 12.06× |
| Packet FIFO | 43 | 66.504 | 4.758 | 13.98× |
| Wrapped async FIFO | 47 | 89.143 | 4.762 | 18.72× |
| Total | 118 | 208.080 | 13.869 | 15.00× |

All screening decisions matched; when both paths executed, cycles, comparison
counts, mismatch counts and first mismatches matched too. There was one paired
run per case on this host. Filesystem caches were not flushed. This is a
throughput result for this complete-pool workload, not a claim of 15× faster
end-to-end AI repair, broad RTL generalization or a first scientific algorithm.
Compiler-selector schemes have prior art in mutation testing; see the
[mutation-schemata implementation discussion](https://onlinelibrary.wiley.com/doi/full/10.1002/stvr.1865).

## Scope and provenance

The three UI examples and wrapped async timing case use the existing V2
research-adapted historical corpus from
[RTL-Repair](https://github.com/ekiwi/rtl-repair) at
`71e1afc0b9a2327d008b46acd415cf3f0343a938`. The selected Verilog-axis files retain
Alex Forencich's MIT notices and their artifact BSD notice. The unchanged V2
evaluator, expected-value seals, source policy, masks and independent frame-byte
guard remain in place. The runtime instruments and harness are project-authored.

These are fixed profiles with declared initialization and valid-qualified
outputs, not independent protocol proofs for every module, arbitrary RTL support,
real CDC/metastability checks or unbounded correctness. The cases are known
development material and may be in model training. Prior weak/negative model
comparisons remain separate and are not replaced by a three-example success rate.

## Packaging and deployment

The default image now includes the exact Verilator 4.038 Ubuntu amd64 package,
verified against SHA-256
`3ed130509d5493a3c95e7be97a00cfed7457b2aeb9c11eed96ea3a802c310836`,
plus g++ and make. Native rechecks were executed inside a read-only, no-network
container using the documented namespace options and an executable results
volume. No key or existing spend state is embedded.

The public test build should default to saved model runs and native checks.
New paid requests require server opt-in and persistent spending state. Public
repository/hosting/YouTube publication remain pending until actual URLs exist.
