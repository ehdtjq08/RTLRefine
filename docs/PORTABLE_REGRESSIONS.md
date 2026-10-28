# Keep the bug from returning after export

The FIFO workflow exports executable regressions with the checked project.
Expectations are calculated from the contract and input stimuli, never copied
from a failing DUT's outputs. Benches check ready, valid and valid payloads
before and after each positive edge.

## One command outside the application

From the extracted checked-project root:

```sh
python3 -I rtlrefine_regressions/run.py --report regression-report.json
```

Requirements: Linux, Python 3.10+, Icarus Verilog/vvp, bubblewrap and prlimit.
The Docker test build supplies the native tools. No API key, model request,
Streamlit or Yosys is needed for this finite suite. Python's `-I` mode prevents
project-local files from shadowing standard modules. Native tools run with
namespaces, readonly inputs, resource limits and no inherited API credentials.
Missing isolation is a setup failure; there is no unisolated fallback.

Exit 0 means every bundled regression completed and passed. Exit 1 means an
assertion failed. Exit 2 means configuration, integrity, setup or verification
was incomplete. Timeout and missing completion are never passing results.

Design source may change. Every run compiles a fresh snapshot and reports its
hashes. The compile configuration, contract, benches and runner are fixed;
regenerate the bundle through RTLRefine if those settings change. This suite
covers finite inputs; use the full check for original benches and properties.

## What is included

- Independently reproduced public counterexamples.
- An upfront contract sequence covering full capacity, stalls, simultaneous
  transfers, repeated reads and reset after traffic.
- Self-checking Verilog benches, a standard-library Python runner, its manifest
  and the generated tools' license. Original source/test assets are preserved.

Earlier public traces survive reimport and are deduplicated. Only public failures
can expand the suite before selection. Final audits cannot revise a candidate.
Export requires the exact bundled standalone script to pass in isolated Python.

The tool-owned `rtlrefine_regressions/` folder is reserved. Modified checker files
or unexpected files stop verification before inference. Uploaded Python is never
executed: the controller verifies the runner against its canonical implementation.
Opening the ZIP through either `/project` or `/properties` retains the stronger
FIFO verification path; the generic page cannot ignore these regressions.

A failing original is also downloadable with tests for local reproduction.
It is labeled as failing input, separately from the accepted project.

## CLI

```sh
# Full testbench, property and regression verification:
python3 -m rtl_agent.property_repair check --project checked.zip --output results/full-check
# Finite regressions only, without a model request:
python3 -m rtl_agent.property_repair regress --project checked.zip --output results/regressions
```

Regressions complement the bounded checks. They do not establish unbounded
correctness, timing, physical CDC safety or unseen repair accuracy.
