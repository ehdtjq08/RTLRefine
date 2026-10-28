# Run and deploy RTLRefine

For the current submission, start with [the judge quickstart](JUDGE_QUICKSTART.md).
The homepage is the repair studio, and `/project` accepts uploaded multi-file
Verilog/SystemVerilog designs with their own self-checking benches. The Docker
test build supports both paths. Earlier archive pages have narrower contracts.

The current `/properties` path also configures FIFO ports from elaboration,
checks an independent contract and exports portable regressions. The standalone
runner needs Linux, Python, Icarus, bubblewrap and prlimit, but no API key, app
package or Yosys. Checked exports keep their stronger checks through `/project`.

The current homepage is the guided repair studio. The image now installs g++,
make and checksum-pinned Verilator 4.038 through
`scripts/install_verilator_pinned.py`, and can run the new native checks.
This supersedes the earlier image limitation below. Compose's persistent results
volume is executable. When testing a read-only image with tmpfs, explicitly use
`--tmpfs /app/results:rw,exec,mode=1777,size=256m`; a noexec tmpfs can compile a
binary but cannot execute it. See [the current studio](REPAIR_STUDIO.md).

The current submission entry is `rtl_app.py`. The existing `app.py` retains older
experiments. Archive pages include the editable sequential workspace,
three historical stream cases, a synthetic queue challenge, an external ZipCPU
UART case and the frozen NVIDIA comparison. UART runtime checks need its public
contract and candidate, not maintainer-fixed RTL. The image excludes the corrected
UART and failed-calibration source copies.

The new `/search` page presents a recorded same-pool comparison of deterministic
candidate order and NVIDIA ranking. Rechecking selected source uses the same V2
native tools and makes no model call. The default container can browse records,
pools, plans and downloads; the native recheck button stays disabled if pinned
Verilator 4.038, g++ and make are absent. No SMT backend is claimed.

## Native Linux

Use the pinned tool versions in `environment.yml`, install bubblewrap and
util-linux through the host package manager, then install `requirements-ui.lock`.
The required EDA tools are Yosys 0.51, Icarus/vvp 11.0, bubblewrap and prlimit.
The older stream, queue-contract and UART workers do not need Verilator, Vivado
or a physical FPGA. Fresh native checks in the new known-bug comparison require
Verilator 4.038, g++ and make in addition to the tools above. Its published traces
use two-state zero-initialization semantics. The default container can browse
the recorded comparison; the new native-check button stays disabled if those
pinned native tools are unavailable. Other Icarus/Yosys workspaces remain usable.

```sh
python3 -m pip install -r requirements-ui.lock
python3 -m streamlit run rtl_app.py
```

The host must permit unprivileged user, mount, network and PID namespaces.
The app checks this boundary and disables execution if it is unavailable. There
is no unisolated execution fallback for uploaded/model-produced RTL.

## Container

```sh
docker compose up --build
```

Open http://127.0.0.1:8501. The image is non-root, has no API key or `.env`, and
defaults to no live model requests. Named volumes retain results and budget state.
The context allowlist excludes keys, original spending state, installed tools,
unrelated prototypes and virtual-machine artifacts.

Nested bubblewrap needs the compose security options for namespace operations
and a fresh proc mount. These do not add SYS_ADMIN or use privileged mode. The
same Docker host was tested with these options and `--network none`: all three
maintainer controls passed inside their isolated EDA workers. The host's kernel
must still support unprivileged namespaces; generic restricted serverless
containers may disable the feature. Upstream context:
https://github.com/containers/bubblewrap/issues/505

The image uses the verified micromamba image digest and resolved Python package
versions. Build activation follows the upstream documentation:
https://micromamba-docker.readthedocs.io/en/latest/quick_start.html

## Optional live NVIDIA repair

Set the server's `NEBIUS_API_KEY` and `RTLREFINE_ENABLE_LIVE_MODEL=1` through the
hosting platform's secret/environment settings. Never place the key in a source
file, image, browser bundle or evidence ZIP. The supported case agent uses
`nvidia/Nemotron-3-Ultra-550b-a55b` through Nebius Token Factory; the catalog is
verified before inference. A repair action permits at most two bounded requests,
with only public feedback available for the second attempt.

Persist the existing `.state/spend.json` when reusing the development account
key, and keep that state across restarts and replicas. Do not reset or publicly
commit the ledger. Costs are estimates based on reported usage and official
rates, not an account billing API. Unknown requests retain reservations.

## Public release status

The source repository is public at https://github.com/ehdtjq08/RTLRefine .
The versioned Docker test build has [judge instructions](JUDGE_QUICKSTART.md).
Saved model runs and fresh local checks require no key. The
[YouTube demonstration](https://youtu.be/JEvktXDIUd0) has been uploaded. See
[publication status](PUBLICATION.md) for its latest visibility check. A separately
hosted application has not been provided. Do not describe this local owner
instance as a public inference endpoint.

The final submission must keep the free test build accessible through judging
and include the actual public repository/video links. The official requirements
are at https://nebiusglobalaihackathon.devpost.com/rules .
