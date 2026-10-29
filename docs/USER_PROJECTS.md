# User-supplied RTL projects

Newly checked general projects include a separately executed standalone checker
and GitHub Actions workflow. Reintroducing a defect fails the same provided
tests without the app or an API key. See [reusable project CI](GENERAL_PROJECT_CI.md).

For compatible single-clock ready/valid FIFOs, `/properties` adds an independent
contract and replayed counterexamples beyond the supplied tests. See
[FIFO property repair](PROPERTY_REPAIR.md). The general workflow below continues
to use the user's own benches without assuming that FIFO contract.

Exports containing `rtlrefine_regressions/` keep their independent FIFO contract
and retained regressions when reopened here. The generic page routes them through
the stronger check; it does not silently ignore the bundled tests.

Open `/project` to upload an RTL ZIP and its own self-checking Verilog/SystemVerilog
testbenches. This path does not select a built-in module, load a corrected RTL
oracle or use the three-example trace harness. The existing example workspace
is still available separately.

## What changed

- Multiple design files and includes, user-selected top, preprocessor defines,
  parameter settings, read-only dependencies and editable-file roles.
- Icarus four-state testbench-driven simulation: no C++ 64-bit-port limit or
  single declared-clock input driver. Functions/tasks and supported SystemVerilog
  constructs can be used in the design. Timing comes from the submitted bench.
- NVIDIA proposes original-file line edits, including logic/operator changes
  outside the old finite patch grammar. Only declared editable design files may
  change. Public failures may be used for one revision, at most two paid calls.
- The selected files are rebuilt independently and every submitted testbench is
  run. Additional `audit` benches are withheld from the model, and their failure
  is terminal. A previously passing verdict is hidden when the uploaded project
  or its configuration changes.

This is a more general project input/verification workflow, not a promise to
repair every hardware design. It needs a meaningful testbench supplied by the
user. A natural-language contract helps diagnosis but does not replace an oracle.

## ZIP format

Include `rtlrefine.json` at the ZIP root. A single enclosing directory is also
accepted. Without a manifest, the web importer lets you select file roles, top
modules, completion markers and additional benches, then inspect/override JSON.

```json
{
  "schema_version": 1,
  "name": "My design",
  "dut_top": "my_top",
  "rtl_files": ["rtl/math.sv", "rtl/my_top.sv"],
  "editable_files": ["rtl/math.sv"],
  "include_files": ["include/widths.svh"],
  "include_dirs": ["include"],
  "data_files": [],
  "defines": {},
  "dut_parameters": {"WIDTH": 129},
  "contract": "The output equals a+b modulo 2**WIDTH.",
  "tests": [
    {
      "id": "basic",
      "phase": "public",
      "top": "tb_public",
      "files": ["tests/public.sv"],
      "success_marker": "PASS"
    },
    {
      "id": "stress",
      "phase": "audit",
      "top": "tb_stress",
      "files": ["tests/stress.sv"],
      "success_marker": "PASS"
    }
  ]
}
```

`rtl_files` preserves compile order (put packages before their consumers).
`include_files` declares design-only headers; a test can declare its own
`include_files` and `data_files`. Shared design ROM data belongs in project-level
`data_files`. Test-only files cannot also be design files or editable. The model
sees editable/design dependency text and public benches; audit benches and their
data are not included. Read-only dependencies over 24 KB are summarized to headers
for the model while their full submitted contents are still compiled.

`dut_parameters` configures standalone elaboration. A test's `parameters` object
overrides parameters of that testbench top. Configure instantiated DUT parameters
in the bench normally; actual numeric DUT parameters and port widths are read
from the compiled design, and standalone elaboration is repeated for those values.

The editor preserves module/package headers, port declarations, default
parameters, type declarations, preprocessor directives and clock/reset event
forms. The user can supply a different configuration in a new project; the
repair agent cannot silently redefine that configuration.

## Explicit test completion

A zero simulator exit by itself is **not** an accepted test. Use either:

1. An existing literal `$display("PASS")` or `$write("PASS")`, with the matching
   `success_marker`. It must be printed only after all checks pass. The worker
   tags that display literal with a fresh nonce in its immutable execution copy.
   The original project testbench is unchanged. It reports a completion marker,
   not an invented assertion count.
2. For new benches, include the runner-provided checker header and count actual
   expectations:

```verilog
`include "rtlrefine_check.vh"
// ... drive the DUT and compare with !==; use $fatal(1, ...) on failure ...
`RTLREFINE_DONE(check_count);
```

With the macro, `minimum_checks` defaults to 1. The private per-execution nonce,
normal exit, absence of `$error`/`$fatal` diagnostics and completion criterion
must all agree. An absent marker, zero checks, timeout or execution failure is
not a pass. A declaration comment alone cannot produce a completion receipt.
The helper header is provided by this runner; do not add a same-named file to
the ZIP. Exported macro-based projects can be rerun through the same CLI below.

The submitted testbenches are the user's oracle. The tool cannot determine that
the user wrote a complete or correct specification. One supplied test means one
supplied test, not three checks or an unbounded equivalence proof.

## CLI and examples

```bash
python3 -m rtl_agent.project_repair example --kind wide_math --output wide.zip
python3 -m rtl_agent.project_repair check --project wide.zip --output results/check_wide
# Explicit paid action, at most two requests:
python3 -m rtl_agent.project_repair repair --project wide.zip --output results/repair_wide
```

Actual development demonstrations:

- A 129-bit, two-file design with a synthesizable arithmetic function: NVIDIA
  replaced subtraction with addition, then passed a two-expectation public bench
  and a 40-expectation audit bench. One actual request, about 2.84 seconds.
- An 80-bit design with two separately driven clocks: NVIDIA corrected the
  second counter's step, then passed public and additional sequence checks.
  One actual request, about 2.62 seconds. This is digital simulation, not physical
  CDC or metastability verification.
- Browser import used different module names and 257-bit ports, verified and
  exported the project, preserved its license file, exercised the no-manifest
  wizard, and hid a previous acceptance when a failing ZIP was uploaded.

These are authored integration/development examples. They do not establish an
unseen repair accuracy or a real-world project success rate. Both actual NVIDIA
patch ZIPs were reimported and rechecked by the final verifier without another
model request. The old 15× complete-pool screening result does not apply here;
this mode uses independent Icarus builds and user benches.

## Limits and isolation

The first version targets Icarus-compatible Verilog/SystemVerilog. VHDL, encrypted
vendor IP without a compatible simulation model, DPI/foreign code, arbitrary
build scripts and every SystemVerilog feature are not supported. Missing files,
tool isolation failures and known unsupported features produce explicit results.
DUT timing delays and simulator-control/host-file/process tasks are restricted;
literal `$readmemh`/`$readmemb` paths must be declared design data. Normal DUT
diagnostic printing does not grant a test pass.

Uploaded files are not executed as shell scripts. Native commands are closed,
run without network/API keys, and mount submitted inputs individually read-only.
Benches may write VCD/log output within the isolated working directory. The
preprocessed testbench is checked for unsupported host/process tasks. Original
and executed marker-transform hashes, tool logs, line edits and source/archive
hashes accompany the result.

Limits: 10 MiB ZIP, 32 MiB expanded, 256 entries, 4 MiB per file, 12 editable
files and 240 KB editable context. There can be 1–8 benches; each has a 0.1–30 s
wall limit. Native commands have CPU, 2 GiB address-space and 16 MiB output-file
limits. Repair context is capped before sending inference, and the existing
$50 total / $20 development ledger remains active. Uncertain model requests
are never automatically repeated.

Only declare source/test files that you intend to check and, for an explicit
NVIDIA repair, send as public context. Remove credential files from archives;
known `.env`, `.git`, `.ssh` and `.aws` paths are rejected. Licenses and unexecuted
project assets are retained for round-trip export. The checked-project download
is offered only after every provided bench passes and its archive hash matches.
