# Automated first-use workflow audit

This is an automated browser and native-tool audit, **not an external human user
study**, repair benchmark or additional hardware example. It reuses the existing
public 129-bit importer fixture. RTL and assertion bytes are preserved; files are
placed in ordinary `src/` and root-level `sim/*_tb.sv` paths without a manifest.
The second scenario materializes the literal-completion variant already covered
by the existing importer tests. It exercises the same design, not a second
independent project.

## Observed friction and fixes

| Point | Before | Current behavior |
|---|---|---|
| Initial file roles | The published v1.6.0 Docker build guessed root `sim/public_tb.sv` and `sim/stress_tb.sv` as design files, then said no bench was supplied. | Common simulation/test directories, `*_tb` names and bench module names suggest bench roles. Users can review and override the suggestions. |
| Existing completion text | A non-macro bench defaulted to `PASS`, requiring manual lookup for an existing `ALL_TESTS_PASSED` literal. | An unambiguous existing success literal is suggested. The selected source can be previewed before setup succeeds. No assertion or completion statement is inserted. |
| Understanding a failure | The assertion diagnostic was behind the native-log expander. | The first failing bench and its actual diagnostic appear directly in the result, with all logs still available. |
| Failed recheck after success | A runtime exception could leave the previous same-input success in session state. | Starting a new check clears the previous receipt. A controlled test-only backend exception confirms no stale success or checked download remains. |

The exception is injected only in a private test-server wrapper. It is not a
production switch or a claim that a real customer experienced an outage. The
product contains no injected-failure path. The native admission checker, policies,
immutable tests, completion nonce and exported CI engine are unchanged.

## Completed paths

Both completion formats pass this sequence in the real browser:

1. Enter the project workspace through the homepage link.
2. Upload the existing source/bench ZIP without writing JSON; review the two RTL
   files, public bench and additional audit bench.
3. Run native verification and the exact standalone export gate.
4. Download the checked ZIP and its evidence; compare every original input byte.
5. Extract the ZIP and run its actual isolated-Python checker, including JUnit.
6. Reintroduce the known arithmetic defect in editable RTL, then restore it:
   standalone exits **0 → 1 → 0** with checks unchanged.
7. Upload the defective export: the old download is hidden and its assertion is
   visible. Reimport the checked export and verify it again.
8. Inject a controlled backend error on an unchanged upload and confirm the
   preceding success is cleared.

Both paths make **zero model requests** and preserve the spending ledger. These
checks demonstrate the stated workflow and regressions, not human learnability,
external adoption, unfamiliar-project success rates or complete test oracles.

Run `scripts/check_first_use_browser.py` against a local test build with Chrome
and Playwright installed to repeat the normal paths. Its optional `--fault-flag`
is for an explicitly instrumented test server; it does not enable failure
injection in the product. Private test inputs/screenshots are not counted as
public demonstration projects. The release receipt records the results.
