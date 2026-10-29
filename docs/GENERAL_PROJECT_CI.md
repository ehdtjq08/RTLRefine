# Reusable checks for general RTL projects

Every newly checked general project now exports a verified standalone runner and
GitHub Actions workflow. This extends reusable regression checking beyond the
FIFO contract. Verification remains exactly the supplied meaningful benches;
the tool does not generate an independent specification for an arbitrary design.

## Export and run

1. Upload a project at `/project`, configure its source/test roles and check it.
2. The normal checker runs every provided test. The app then runs the exact
   exported Python script against the exported source as a separate final gate.
   A failure at either gate prevents the checked ZIP download.
3. Extract the checked ZIP and run from its root:

```sh
python3 -I rtlrefine_ci/run.py
```

The runner uses Python's standard library and a small, hash-verified copy of the
existing RTLRefine checker. It needs no app installation, Streamlit, Yosys,
provider credential or inference request. It requires Python 3.10+, Linux,
Icarus (`iverilog`/`vvp`), bubblewrap and `prlimit`, with unprivileged namespaces
permitted by the host. Native workers have read-only inputs, no network or API
credentials, and the same resource limits as the application checker.

| Exit | Meaning |
|---|---|
| 0 | Every provided test passed. |
| 1 | Design regression, RTL compilation failure or changed DUT interface. |
| 2 | Setup, integrity, unsupported or inconclusive verification. |

JSON and JUnit outputs default to `rtlrefine-ci-report.json` and
`rtlrefine-ci-junit.xml`. `--report`, `--junit` and `--root` override locations.
Declared inputs and runner files cannot be overwritten by a report argument.
Every run compiles current sources afresh; editing RTL cannot reuse an older pass.

## GitHub Actions

Commit the extracted project at your repository root, including the hidden
`.github/workflows/rtlrefine.yml`. It installs the native tools on Ubuntu 22.04,
runs the same isolated-Python command on pushes and pull requests, and uploads
JSON/JUnit reports even when checking fails. It uses exact action commit pins,
read-only repository permission, no persisted checkout credential and no secrets.
The workflow never requests inference or rewrites the RTL.

The runner's manifest and engine hashes are embedded in the generated script.
Testbench/configuration/read-only dependency changes require review and a fresh
export. Editable design files may change. Numeric elaborated interfaces remain
bound to the checked profile. The app validates imported bundles before any
model call; it never executes an uploaded replacement Python script. Intentional
changes to checks can be made from the original project and exported as a new
bundle. Normal repository review protects deliberate changes to the runner and
workflow; these hashes are not a signed or tamper-proof policy.

## Reproducible examples

`demo/general_project_ci` contains three checked exports:

- An actual prior NVIDIA-selected repair of the known upstream verilog-axis
  early-ready regression: eight benches, 30,493 assertion evaluations.
- An authored 129-bit, two-file arithmetic example: two benches, 42 assertions.
- An authored 80-bit example driven by two clocks: two benches, 27 assertions.

No new model request was used to package these. The arithmetic and counter fixes
are supplied healthy integration fixtures, not new AI repair results. The
two-clock example is digital simulation, not physical CDC verification.

```sh
python3 -I scripts/check_general_project_ci.py --output results/general-ci-cycle
```

This script imports no RTLRefine or third-party Python. For each exported project
it executes the exact runner on checked source, reintroduced bug and restored
source, requiring exit codes **0 → 1 → 0**. Changing a protected audit instead
requires exit 2. The repository's own Actions workflow runs this cycle too.
The examples retain their original third-party source and license notices.

Earlier recorded ZIPs remain unchanged; recheck them in the current application
to obtain a fresh CI-enabled export. FIFO exports continue using their separate
contract and retained-counterexample suite. Mixed FIFO/general bundles are
rejected rather than silently dropping either suite.
