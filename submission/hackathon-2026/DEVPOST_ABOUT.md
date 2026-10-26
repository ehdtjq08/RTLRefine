## Inspiration

An RTL change can look reasonable and still mishandle a packet boundary or leave
stale state after reset. Debugging that failure means moving between code,
simulation output and testbenches. I wanted an AI repair workspace that keeps
those pieces together and lets another engineer rerun the exact proposed change.

## What it does

RTLRefine is a browser tool for Verilog/SystemVerilog repair, powered by NVIDIA
Nemotron 3 Ultra through Nebius Token Factory.

Upload a ZIP containing design files and self-checking testbenches. Select file
roles in the browser or include a project manifest. The tool reproduces the
public failure, asks Nemotron for edits to the allowed design files, then
independently rebuilds the selected source and runs every provided bench. Extra
audit benches stay hidden from the model until selection is fixed. A failed
audit ends the attempt and prevents a checked-project download.

The importer supports multiple files, parameters, functions and bench-driven
clocks within Icarus's supported language subset. It has no built-in module-name
whitelist. Downloads preserve the user's project assets and include a separate
evidence archive with source hashes, tool logs and model responses.

The homepage also provides three historical stream-processing examples, with
captured signal comparisons beside the exact source diff. Their bounded repair
pools use a faster screening path.

## How I built it

Python coordinates Streamlit, the Nebius API and isolated native workers. In the
upload workflow, Nemotron proposes original-file line edits and can revise once
using public test results. The model cannot edit testbenches, change ports or
parameters, or inspect audit inputs. Native workers run without network access
or API credentials. Explicit test completion and source hashes prevent an empty
simulation or stale success from becoming an accepted result.

For the historical examples, compatible patch candidates share a compiled
simulation through a runtime selector. An inactive-source control checks the
screening representation; incompatible candidates use separate builds. Final
acceptance always rebuilds the exact uninstrumented source independently.

Across the same 118 candidates, separate builds took 208.08 seconds and shared
screening took 13.87 seconds, with matching results: 15.0x complete-pool screening
throughput. This was one paired run per historical profile on this host. It
measures that screening stage; the uploaded-project workflow uses independent
Icarus builds and does not inherit the speed result.

## Challenges

An early response spent its output budget on reasoning and returned incomplete
JSON. Compact context and direct structured responses made the bounded workflow
more practical. Plausible incorrect diagnoses also made it necessary to label
model explanations as hypotheses and use executable checks for acceptance.

Supporting user projects required preserving compile order, dependencies and
parameterized interfaces while keeping the tests immutable. The importer also
had to distinguish successful test completion from a simulator that simply
exited. Earlier failed requests and negative studies remain in the repository.

## What I learned

Compiler work can dominate a repair search. Sharing compatible builds improved
one measured stage substantially, while independent final compilation retained
a direct connection between the downloaded file and its checks. The rejection
path also became useful: a partial reset fix passes the public trace but fails
the additional profiles, and the UI shows why export is blocked.

## What's next

The current demonstrations include historical defects and authored integration
examples with wide arithmetic and independently driven clocks. Verification
covers the supplied tests; its value depends on their quality. It does not
establish unbounded correctness, physical CDC safety or synthesis timing.

I want to evaluate repair quality on new projects with independent RTL designers
and add further simulator support. The public test build already supports
credential-free review of recorded NVIDIA runs and fresh native verification.
