# Third-party RTL

The historical UART pair under `external_cases/uart_bitorder_external` comes
from Alex Forencich's MIT-licensed verilog-uart at commits 62eb6f5d45b6 and
db0017a22c57. Original headers and the full `UPSTREAM_LICENSE` are retained.
The same notices accompany derived selected source in `demo/uart_peer` and
`demo/general_project_ci/uart-peer`. The stateless packaging adapter and peer
testbench are RTLRefine-authored; see `docs/UART_PEER_VALIDATION.md` for scope.

The repair studio uses locally bundled Inter and IBM Plex Mono fonts from
Google Fonts under the SIL Open Font License. Original notices, source URLs,
hashes and generated WOFF2 assets are retained in `assets/fonts`. Runtime font
loading makes no external request.

`research/ranking_holdout` and `demo/evidence_ranking` add commit-pinned
`axis_rate_limit`, `axis_stat_counter` and `i2c_master` under their upstream MIT
notices, and ZipCPU/wb2axip `skidbuffer` under Apache License 2.0. The full
Apache license is retained beside the original source. Project-authored
evaluation helpers blank only the inactive FORMAL appendix and inject labeled
RHS-to-zero synthetic faults. Source-only candidate edits and a seeded inverse
are recorded separately from their upstream versions; all attempts and full
original/modified source are retained with hashes. These are constructed
ranking tasks, not newly discovered upstream bugs. See
[the ranking study and source commits](docs/EVIDENCE_RANKING.md).

`demo/repair_search` retains generated derivatives of the same licensed sources
used by V2. The project-authored grammar generated source before model ranking;
NVIDIA selected existing IDs rather than writing RTL. MIT/GPL notices, full
original/modified corresponding source and BSD artifact attribution remain.
The selected one-bank byte-order edit is not presented as all-bank correctness.

`external_cases/known_bugs_v2` and `demo/known_bug_comparison_v2` (and the separately retained superseded V1 versions) include research-adapted
historical versions from https://github.com/ekiwi/rtl-repair at
`71e1afc0b9a2327d008b46acd415cf3f0343a938`. Verilog-axis source retains its MIT
notices; ZipCPU SPI source and model-edited derivatives retain
**GPL-3.0-or-later**. Every sealed case includes the applicable full `LICENSE`;
the original/modified corresponding source and modification notice accompany
the recorded evidence. Project-authored wrappers are MIT. Xilinx-generated
examples with unclear distribution licensing were excluded. See
[the V2 benchmark protocol](docs/KNOWN_BUG_BENCHMARK_V2.md).
The research artifact declares BSD-3-Clause in its [Zenodo record](https://doi.org/10.5281/zenodo.10904586); metadata/license verification and the full BSD notice are retained under `research/known_bug_benchmark`. Vendor source retains its separate MIT/GPL terms.

`third_party/wbuart32_cts`, `external_cases/wbuart32_cts`, and derived `txuart.v`
files in `demo/external_uart` come from https://github.com/ZipCPU/wbuart32. They
are copyright Gisselquist Technology and **GPL-3.0-or-later**. Original notices,
full GPL `LICENSE`, complete corresponding source, pinned provenance and a
modification notice accompany the evidence. The project's MIT license does not
replace this license. See [the external UART case](docs/EXTERNAL_UART.md).

The commit-pinned sources under `third_party/verilog_axis_reset`,
`third_party/verilog_axis_adapter_keep`, `third_party/verilog_axis_frame`, and the qualification-only
`third_party/verilog_axis_pipeline` come from
https://github.com/alexforencich/verilog-axis. Each directory contains the
upstream MIT `COPYING`, original source headers, and a `source.json` identifying
the original and fixed commits and source hashes. The original/fixed copies and
model-edited derivatives in the recorded evidence retain these notices. These
are historical public bugs, not newly discovered vulnerabilities or defects.
The pipeline qualification candidate is not presented as a verified data-loss
case: its independent conservation regressions did not fail.

The files in `third_party/nvdla` are original NVDLA sources from
https://github.com/nvdla/hw at commit
`1a65f1f5b48268accaa47c95f95c2601918be095`.

They retain NVIDIA's original notices and are distributed with the
**NVIDIA Open NVDLA License and Agreement v1.0**, reproduced in
`third_party/nvdla/LICENSE`. The repository's MIT license does not replace that
license for these files or their derivatives.

`external_cases/*/baseline.v` files are annotated derivatives. Their changes
fix the original default parameters and rename the top module. The original
arithmetic expressions remain intact, and a separate formal bridge checks each
adapter against the untouched upstream module plus its parameter wrapper.

Recorded external NVIDIA proposals carry an added attribution and modification
notice. Their raw provider text, the executed-file hash, and the additive notice
transformation are recorded separately. No functional source repair is inserted
by the controller.

The Nangate45 library is fetched separately under its recorded platform license.
Library binaries/data and installed EDA tools are excluded from source bundles;
the pinned URL, hash and setup helper are supplied for reproduction.

The source in `external_cases/axis_register_external/*/rtl/axis_register.v` is
commit-pinned Alex Forencich verilog-axis RTL, copyright 2014–2018, under its
retained MIT header and `UPSTREAM_LICENSE`. Original and NVIDIA-edited copies in
`demo/external_rtl_validation` retain that header. The selected edit repairs a
known upstream early-ready throughput regression, not a newly discovered bug.

`external_cases/zipcpu_skid_external/rtl/skidbuffer.v` is unmodified ZipCPU
wb2axip RTL, copyright 2019–2025 Gisselquist Technology, LLC. Its header specifies
Apache License 2.0; the official license text accompanies it. The stateless
adapter's verilog-axis-derived interface retains the MIT notice and the
RTLRefine-authored adapter body is MIT. The repository's MIT license does not
replace the Apache terms of the upstream skid buffer. Exact revisions, hashes
and validation scope are in `docs/EXTERNAL_RTL_VALIDATION.md`.
