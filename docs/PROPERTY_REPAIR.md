# Find failures beyond a passing FIFO test

Open `/properties` from the homepage. The existing `/project` route continues to
support uploaded projects and their own benches. The new route adds an explicit
independent contract for a supported class of ready/valid FIFO.

The default example's four smoke expectations pass. A bounded symbolic check
still finds a five-state failure: after the accepted words have been consumed,
the original design keeps output-valid asserted. The exact SAT inputs reproduce
that failure in Icarus against a separate Python queue. NVIDIA receives the
public contract and that reproduced failure, then proposes edits to design files.
The selected files are independently rebuilt for the original tests, withheld
sequence bench, deeper bounds and a reachable progress sequence.

## What the contract means

- One positive-edge clock and synchronous active-high reset, which flushes data.
- No empty fall-through. Output-valid matches occupancy; accepted data leaves in
  order. The output stays stable while stalled.
- Input-ready means room is available or an output transfer frees room in the
  same cycle. FIFO variants with different ready/latency policies need a different
  contract; they are not automatically classified as defective.
- Every DUT port must map to the eight interface signals below, with the declared
  widths. A multi-file implementation or wrapper can be used; compiled state
  must share the same positive-edge clock. Asynchronous state, latches and
  multiple clocks are unsupported here.

Include `fifo_contract.json` alongside `rtlrefine.json` and your sources/benches.
Alternatively upload sources and benches without either JSON file. The browser
can configure file roles, inspect the actual DUT ports without a model request,
map the eight signals and set capacity. It writes both configurations into the
downloadable project. Port inspection alone does not verify the contract.

Example contract:

```json
{
  "schema_version": 1,
  "kind": "ready_valid_fifo",
  "ports": {
    "clk": "clk", "rst": "rst",
    "s_valid": "s_valid", "s_ready": "s_ready", "s_data": "s_data",
    "m_valid": "m_valid", "m_ready": "m_ready", "m_data": "m_data"
  },
  "data_width": 4,
  "depth": 4,
  "discovery_steps": 12,
  "audit_steps": [16, 20]
}
```

The right-hand port names may be your own names. Numeric DUT parameters come
from the project manifest. Supported input limits are width 1–16, capacity 2–8,
discovery 4–24 states and one or two deeper audit bounds up to 40. These are
resource ceilings, not a promise that every accepted input finishes: a timeout
or unknown result is UNPROVEN and blocks export. The demonstrated bounds are
12 for discovery and 16/20 for final checks, including the first reset state.

DUT formal directives, checker assumptions, attributes, simulator tasks and
explicit X/Z literals are rejected before inference. The model cannot edit the
contract, port declarations, parameters or testbenches. Additional audit source,
results and depths are omitted from its context; final rejection is terminal.

## Use without an API key

The default Docker build has new inference disabled. It includes the actual
NVIDIA result and native checks. Run **Find hidden failures without NVIDIA** to
reproduce the original defect, **Show saved repair and evidence** to inspect the
recorded response, and **Recheck exported project without NVIDIA** to verify the
downloaded source again. A changed project or contract hides old acceptance.

Checked exports retain executable public regressions. Run the included script
outside the app or use the standalone-run button. Source changes compile afresh;
changed checker files or configuration stop validation. Both project routes
honor an inherited regression suite. The original failing project is separately
downloadable for reproduction. See [portable regressions](PORTABLE_REGRESSIONS.md).

Optional designer edits preserve the input interface, parameters, clock/reset
forms and license header. Compiler diagnostics are shown directly and guide a
model revision. Original and selected sources also have mapped 7-series resource
diagnostics; these estimates are independent of correctness acceptance.

```sh
python3 -m rtl_agent.property_repair example --output fifo.zip
python3 -m rtl_agent.property_repair check --project fifo.zip --output results/fifo-check
# Explicit paid action; at most two requests under the persistent budget guard:
python3 -m rtl_agent.property_repair repair --project fifo.zip --output results/fifo-repair
```

## Evidence and limits

The demonstration cohort has three authored defects: simultaneous-transfer
occupancy, premature pointer wrap and stale reset state. Each passes its supplied
smoke test and has a separately replayed property failure. A healthy control
passes the final tests and bounds without requesting inference. These are
integration examples, not newly discovered historical bugs or unseen accuracy.

The monitor universally tracks an arbitrary accepted transaction independently
of the DUT's circular addresses. The replay oracle uses a full Python queue.
Final progress requires full capacity, overlap, stall, a watched dequeue, reset
after traffic and a queue-length of reads within a reset epoch. All checks are
bounded, two-state for Yosys and four-state for replay; no unbounded, timing,
physical-CDC or arbitrary-protocol guarantee is claimed. Larger-bound timeouts
and superseded development monitors remain visible. This mode does not use the
earlier 15x shared-compilation screening path.

See [the evaluation protocol](PROPERTY_REPAIR_PROTOCOL.md),
[actual runs and development limits](../demo/property_repair), and
[general project format](USER_PROJECTS.md).

Backend reference: [Yosys 0.51 SAT command](https://yosyshq.readthedocs.io/projects/yosys/en/v0.51/cmd/sat.html).
