## Inspiration

A FIFO can pass a simple read/write test and still miscount when input and output
transfers happen together. An AI patch that passes the same test can leave that
failure untouched. I wanted an RTL repair workspace that could expose the missing
case, show another engineer how to reproduce it, and check the exact exported file.

## What it does

RTLRefine helps developers repair Verilog/SystemVerilog with NVIDIA Nemotron
through Nebius Token Factory. The project workspace accepts multiple source
files and the user's own self-checking testbenches.

Its new FIFO workspace adds an independent external-port contract. It searches
for failures beyond the smoke test, minimizes the failing symbolic bound, and
replays the input sequence in Icarus against a separate Python transaction queue.
Nemotron receives the public contract and reproduced failure to propose a patch.

The selected source is then rebuilt independently for all supplied benches and
deeper bounded checks. A progress check exercises full capacity, simultaneous
transfers, stalls, reads across a queue-length without reset, and reset after
traffic. A failed or unproven final check blocks the checked-project download.

## How I built it

I used Python and Streamlit with Yosys, Icarus, Verilator and isolated native
workers. The FIFO property monitor universally tracks an arbitrary accepted
transaction and its predecessors independently of the DUT's circular addresses.
The replay oracle uses a full Python queue. No corrected reference FIFO is loaded.

The model can edit only permitted design files, with at most two bounded calls.
Audit bench source, results and depths are withheld until selection is fixed.
An audit failure ends that run. Native workers have no network access or API
credentials, and hashes connect source, configuration, evidence and export.

The historical example workspace also shares compiled simulations across
compatible candidate patches. Final acceptance independently rebuilds the
uninstrumented source. Uploaded projects and FIFO property repair use separate
builds and do not inherit that screening optimization.

## Challenges I ran into

Deeper property checks hit time limits. I retained those UNPROVEN results and
made the checked bounds explicit. The current FIFO demonstrations use a public
bound of 12 symbolic states and final bounds of 16 and 20, including the first
reset state. A separate reachability query checks that meaningful traffic occurs.

Supporting user projects also required preserving interfaces and compile order,
rejecting unsupported clock semantics, and preventing the agent from modifying
its checker. A changed source or contract immediately hides an older acceptance.

## Accomplishments I'm proud of

- Three authored FIFO defects pass their smoke tests but produce independently
  reproduced failures within five, six and six symbolic states. The healthy
  control passes without requesting a model repair.
- An actual NVIDIA repair fixes the simultaneous-transfer defect and passes four
  smoke expectations, 65 additional sequence checks and both deeper property
  bounds. Its downloaded ZIP also passes a fresh check without another model call.
- In a separate historical measurement, the same 118 candidates take 208.08
  seconds with individual builds and 13.87 seconds with shared screening:
  15.0x complete-pool screening throughput, with matching results. This is one
  paired run per profile on one host, not end-to-end repair speed.
- The public Docker test build includes recorded model responses and supports
  fresh native verification without an API key.

## What I learned

Better failure evidence can improve the repair workflow before another model
request is made. A concrete input sequence helps explain why the smoke test was
insufficient and gives the designer something that can be replayed independently.

Verification still depends on its contract. The FIFO examples are authored
integration cases, not an unseen accuracy benchmark. Their bounded, synchronous
checks do not establish unbounded correctness, timing or physical CDC safety.
FIFO variants with other latency or ready policies need different contracts.

## What's next for RTLRefine

I plan to evaluate new projects with independent RTL designers, add more protocol
contracts and improve verification scalability. Future comparisons will measure
repair quality, total time and inference cost under matched budgets. Formal
counterexample-guided repair is an established approach; any research novelty
will need a specific new method and evidence against existing baselines.
