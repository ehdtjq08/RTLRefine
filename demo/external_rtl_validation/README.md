# Real external RTL validation records

Two independently authored RTL modules are pinned with original source and
licenses. `summary.json` distinguishes the one actual NVIDIA repair from the
healthy compatibility controls. Source revisions with identical hashes are not
counted as independent implementations.

- `axis_register/`: current healthy, known upstream throughput regression,
  actual NVIDIA repair, fresh export reimport and explicit negative harness.
- `zipcpu_skid/`: unmodified healthy leaf with a stateless metadata adapter and
  an explicit negative observation control. No model request was used.
- `projects/`: importable ZIPs for the ordinary `/project` workflow.

The `PROVENANCE.json` asset in a project describes the originally imported
upstream revision. A checked export can contain selected edits; its exact design
hashes and source changes are in the run's `result.json`. It is not a claim that
the NVIDIA-selected source is byte-identical to upstream. All audit checks here
are finite simulation; see `docs/EXTERNAL_RTL_VALIDATION.md` and the case protocol.
