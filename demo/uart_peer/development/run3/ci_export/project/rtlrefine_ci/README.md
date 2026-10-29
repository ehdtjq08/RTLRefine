# Reusable RTL project checks

From the extracted project root, run:

    python3 -I rtlrefine_ci/run.py

No API key, model request, Streamlit or RTLRefine installation is needed.
Python 3.10+, Linux, Icarus Verilog (`iverilog` and `vvp`), bubblewrap and
util-linux `prlimit` are required. Ubuntu/Debian setup:

    sudo apt-get install iverilog bubblewrap util-linux

The host must permit unprivileged user namespaces. Restricted hosts return
an explicit setup error; there is no unisolated fallback.

Exit 0: every provided test passed. Exit 1: a design regression (including
RTL compilation/interface failures). Exit 2: setup, integrity or unproven result.
JSON and JUnit reports default to `rtlrefine-ci-report.json` and
`rtlrefine-ci-junit.xml`; `--report`, `--junit` and `--root` override paths.

Commit the extracted project at your repository root, including the hidden
`.github/workflows/rtlrefine.yml`. Pushes and pull requests then run the same
command on GitHub Actions and upload both reports, even on failure. The workflow
uses read-only repository permission, no persisted checkout credential, no
secrets and no inference. Review normal CI changes before merging them.

The engine is a byte-preserving copy of RTLRefine's existing checker, policy,
project loader and isolated native runner, with its MIT license. The engine and
manifest hashes are embedded in run.py. Testbenches, read-only dependencies,
configuration and elaborated interfaces are locked; editable RTL can change
and is always freshly compiled. Re-export after intentionally changing checks
or interfaces. Hashes catch accidental drift; repository review protects the
runner and workflow themselves. They are not a signed or tamper-proof policy.

Only hash-verified bundled Python is imported. Uploaded project scripts are
never executed. Native tools receive only declared files, resource limits,
read-only inputs and no network or API credentials. The result covers the
provided finite tests; it is not unbounded protocol, timing or CDC proof.
