# General-project CI exports

`summary.json` records provenance, counts and exact checked ZIP hashes. Each
`project/` directory can be checked directly with isolated Python, without the
application or an API key. Its hidden `.github/workflows/rtlrefine.yml` is the
generated workflow for use in a user's own repository root.

The external AXI source is the **prior** actual NVIDIA-selected known upstream
repair. Packaging it used no new inference. The other two are authored healthy
integration fixtures. They are not additional external repair successes.

Run `python3 -I scripts/check_general_project_ci.py` from the repository root
for all four 0 → 1 → 0 cycles and protected-audit rejection. See
`docs/GENERAL_PROJECT_CI.md` for the contract and limitations.

The added UART pair is an actual prior NVIDIA-selected correction of a known
historical bit-order case. Its six development requests and failures are in
`demo/uart_peer`; packaging and CI make zero additional requests. The earlier
`validation.json` retains the three-case v1.5 snapshot; the four-case result is
`UART_PEER_VALIDATION.json`.
