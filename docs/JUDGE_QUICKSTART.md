# RTLRefine test build

This is the runnable test build for RTLRefine. It runs on a Linux Docker host
with unprivileged user namespaces enabled. No FPGA board or vendor tools are
needed. Restricted container hosts may block the nested isolation required by
the native workers; execution stops explicitly in that case.

## Download and start

[Download the versioned test build](https://github.com/ehdtjq08/RTLRefine/archive/refs/tags/v1.3.0.zip),
extract it, and open a terminal in the extracted directory. Install Docker Engine
and the Docker Compose plugin if they are not already available, then run:

```sh
docker compose up --build
```

The first build downloads the Python and native-tool dependencies and builds
pinned Verilator. Allow several minutes and keep the terminal open. Then open
http://127.0.0.1:8501. This localhost address is the application on your machine;
the public URL above supplies its test build.

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

The original `v1.2.1` test build predates this extension. Download the current
`v1.3.0` source to try it. See [the FIFO contract and limits](PROPERTY_REPAIR.md).

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
