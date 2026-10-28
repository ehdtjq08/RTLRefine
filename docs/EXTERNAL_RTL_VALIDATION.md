# Validation on independently developed RTL

Open `/external-validation` in the current build. The page includes pinned source
links, actual source differences, all profile results, downloadable projects and
fresh native recheck buttons. It never makes a new inference request. The same
projects can be uploaded to `/project` without module-specific checker code.

## Real upstream early-ready regression

The MIT-licensed `alexforencich/verilog-axis/rtl/axis_register.v` has a documented
early-ready change at commit
[`6d4458e5cc15`](https://github.com/alexforencich/verilog-axis/commit/6d4458e5cc15df401b82a8fd615b3216e6a61d0e).
The maintainer reverted it for throughput at
[`b9e0af36341a`](https://github.com/alexforencich/verilog-axis/commit/b9e0af36341a81ae80d6a8467b029d79c69b71cb).
Original headers, full MIT license, commit metadata and byte hashes are retained
under `external_cases/axis_register_external`.

The independently authored public test reproduces the capacity/throughput issue:
with one accepted word and stalled output, an input-idle gap prevents use of the
second skid slot. This is a known historical performance/capacity regression,
not a newly discovered defect or an unconditional AXI protocol violation. An
arbitrary AXI receiver is not required to assert READY whenever space exists;
this test is specific to the advertised two-entry skid-buffer behavior.

The unmodified current source passes all eight profiles. The historical regressed
source fails the public capacity check. A recorded NVIDIA request repairs the
original source through the ordinary project workflow; the exact candidate then
passes eight benches and 30,493 assertion evaluations. Its exported ZIP passes
all eight again with no additional model call. Selected HDL tokens match the
maintainer's reverted logic, although comments differ and file hashes differ.

Current, pre-regression and revert source have identical hashes. They are one
healthy implementation, not three independent projects or accuracy samples.
The assistant inspected upstream history for qualification, so this is not a
blinded evaluation. The corrected source is neither a model input nor the
acceptance oracle; expected behavior comes from the protocol/capacity tests.

## Second independent author: healthy skid buffer

ZipCPU's Apache-2.0 `wb2axip/rtl/skidbuffer.v` is pinned at
[`2e8d3bc2d26d`](https://github.com/ZipCPU/wb2axip/blob/2e8d3bc2d26ddc33d1881022a2a2b9d3f0c16b9b/rtl/skidbuffer.v).
The original leaf is unmodified. A disclosed stateless adapter packs AXI metadata
into its data bus. It passes eight profiles and 30,847 assertion evaluations,
with zero inference requests. This is a healthy compatibility control, not a
bug discovery or repair result.

The independently authored scoreboards check accepted transaction order,
valid-byte-qualified data, sidebands, output stability, reset flushing, drain,
conservation and buffering limits. Profiles span skid/simple/bypass or the
corresponding registered/combinational/passthrough modes and 8/16/32/64-bit AXI
payload widths, including enabled/disabled sidebands and low-power variants.
The ZipCPU leaf's packed bus is wider than the AXI payload.

Both test harnesses also reject an explicit observed-data corruption control.
That control changes only the test observation and is not described as a source
bug. Source, legal input rules, monitor definitions and profiles were fixed and
qualified before the NVIDIA repair request. The final seven audit profiles were
withheld from model context; final rejection would have ended that run.

## Reproduction and limits

```sh
python3 scripts/validate_external_axis_register.py qualify --output results/axis-qualification
python3 scripts/validate_external_zipcpu_skid.py --output results/zipcpu-qualification
```

Actual records and importable ZIPs are in `demo/external_rtl_validation`. The
generic CLI and UI can recheck their checked/source ZIPs without credentials.
No special external-module allowance or evaluator change was needed. These are
finite four-state simulations at stated configurations, not unbounded AXI
verification, physical timing/CDC tests or evidence of general model superiority.
