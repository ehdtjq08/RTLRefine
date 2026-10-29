# RTLRefine test build

This is the runnable test build for RTLRefine. It is tested on an x86-64 Linux Docker host
with unprivileged user namespaces enabled. No FPGA board or vendor tools are
needed. Restricted container hosts may block the nested isolation required by
the native workers; execution stops explicitly in that case.

## Download and start

[Download the versioned test build](https://github.com/ehdtjq08/RTLRefine/archive/refs/tags/v1.6.2.zip),
extract it, and open a terminal in the extracted directory. Install Docker Engine
and the Docker Compose plugin if they are not already available, then run:

```sh
docker compose up --build
```

The first build downloads the Python/native dependencies and checksum-pinned
Verilator binary. Allow several minutes and keep the terminal open. Then open
http://127.0.0.1:8501. This localhost address is the application on your machine;
the public URL above supplies its test build.

## Recheck real external RTL

Open `/external-validation`, where **UART serial peers** is the default tab.
The pinned original TX/RX pair passes a limited closed-loop smoke but reverses
bytes at an explicit LSB-first peer. Inspect the actual captured bits and saved
NVIDIA request metadata. Run the original loopback-only smoke, reproduce the
original independent-peer failure, and recheck the selected two-file repair.
All buttons make zero model requests. The separate exported CI cycle runs the
exact bundled script against checked source, both original vendor files and
restored source, requiring exit codes 0 → 1 → 0.

Six actual development requests, including two failed runs, are retained. The
last two-request run passes eight fixed profiles and the standalone runner.
This is a known historical bit-order change, not new discovery, an introduced
regression or unseen accuracy. See [UART source and scope](UART_PEER_VALIDATION.md).

The other two tabs retain the verilog-axis early-ready throughput regression
and another author's unmodified ZipCPU skid buffer with a disclosed adapter.
Their exact older ZIPs can still be downloaded and rechecked. See
[those earlier external results](EXTERNAL_RTL_VALIDATION.md).

## Keep general RTL checks in CI

Open `/project`, expand **Try a portable example ZIP**, and download the checked external UART pair with CI. It contains the prior actual
NVIDIA-selected repair;
packaging used no additional inference. Upload that ZIP, click **Check this
project**, and inspect both the native verdict and the standalone export gate.
The included Actions workflow can be inspected before downloading the checked ZIP.

Extract the ZIP and run `python3 -I rtlrefine_ci/run.py`. JSON/JUnit reports and
exit codes are 0 for pass, 1 for a design regression and 2 for setup/integrity or
unproven checking. Commit the project including `.github/workflows/rtlrefine.yml`
at your own repository root to repeat this command on pushes and pull requests.
The native tools are required; there is no app installation or API credential.
See [general-project CI](GENERAL_PROJECT_CI.md) for installation and boundaries.

## Review a recorded NVIDIA repair

1. Open the homepage. The packet-FIFO example loads a saved actual Nebius run.
2. Compare the captured failure, proposed source diff and verification receipt.
3. Click **Recheck this exact patch** to compile and rerun the exact file locally.
   This makes no model request.
4. Download checked RTL and verification evidence. Choose the other historical
   examples to inspect their independent profiles and recorded failures.

## Check a project ZIP

1. Open `/project` using the homepage link.
2. Upload `submission/hackathon-2026/examples/wide-math-fixed.zip` and click
   **Check this project**. Both supplied benches should pass. Download the
   checked project and its evidence.
3. Upload `wide-math-original.zip`. The old success should disappear. Click
   **Check this project**; its arithmetic failure prevents a checked download.
4. Upload `wide-math-partial.zip` and check it. This intentionally incomplete
   developer fixture passes the public bench and fails the audit. It is rejected.

The examples are authored integration demonstrations, not a repair-accuracy
benchmark. You can also upload your own Icarus-compatible project and meaningful
self-checking benches. Configure roles in the browser or include `rtlrefine.json`.
See [the project format and supported subset](USER_PROJECTS.md).

## Find a failure missed by a FIFO smoke test

With the current source build, open `/properties`. The default authored FIFO
passes its original smoke test but fails the independent contract in five
symbolic states. Run **Find hidden failures without NVIDIA**, inspect the
reproduced failure, then use **Show saved repair and evidence** to inspect the
actual NVIDIA correction. Recheck the exported project with zero model calls.
The separate healthy control is accepted without requesting a repair.

Run **Run standalone regressions without NVIDIA** to execute the exact exported
script in isolated Python. The checked example returns exit 0; its original
failing reproduction returns exit 1. Download the checked ZIP and run
`python3 -I rtlrefine_regressions/run.py` from its extracted root to repeat the
finite suite without the app, an API key or Yosys. It requires Linux, Python,
Icarus, bubblewrap and prlimit; the Docker build supplies these tools.

Sources and benches can also be uploaded without JSON manifests. Choose file
roles, inspect actual ports, map signals and set the FIFO capacity. Optional
designer edits preserve ports, parameters and clock/reset forms. A source change
or changed contract requires a fresh check.

The original `v1.2.1` test build predates this extension. Download the current
`v1.6.2` source to try all current features. See [the FIFO contract](PROPERTY_REPAIR.md)
and [portable regressions](PORTABLE_REGRESSIONS.md).

## Model access and verification scope

The default test build makes no paid inference calls. Recorded NVIDIA requests,
responses and failed attempts are included, and fresh native verification is
credential-free. The submission video records an actual fresh request through
Nebius Token Factory. A new repair request needs an operator-supplied server-side
credential and explicit enablement; the archive does not contain one. See
[deployment](DEPLOYMENT.md) for the owner setup and persistent budget state.

User-project verification covers only the supplied immutable testbenches. It
does not establish unbounded correctness, timing or physical CDC safety. The
homepage's 15.0x number measures complete-pool screening for three historical
profiles; it does not apply to user-project repair.

## First-use setup

Without a manifest, the importer suggests source/bench roles from conventional
paths and module names and suggests an existing unambiguous success literal.
Review both choices. The selected bench can be previewed before validation
succeeds; failed assertions are shown directly in results. See
[the automated first-use audit](FIRST_USE_AUDIT.md), which is not a human study.

## Execution latency

The application reuses identical DUT-only compiler work within a single checker
call and uses blocking process completion waiting. Actual test compilation,
profile elaboration and simulation remain fresh. Exported CI stays on the
original engine. See [paired measurements and scope](PERFORMANCE.md).
