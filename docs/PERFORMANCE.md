# Measured verification and rebuild latency

The v1.6.2 application reduces native orchestration work. This does not change
NVIDIA prompts/models, test expectations or hardware implementations. The frozen
admission checker, source policy and exported standalone CI engine are unchanged.

## Complete check/export workflow

The immutable v1.6.1 checkout and optimized source received the **same four
existing inputs**, with four paired repetitions per input. Order alternated
reference/optimized and optimized/reference. Every repetition used fresh work
directories. Times include public checking, final tests, the exact standalone
export gate and packaging; they exclude inference and browser/network latency.

| Existing input | Reference median | Optimized median | Elapsed reduction |
|---|---:|---:|---:|
| AXI register | 2.709 s | 2.184 s | 19.4% |
| 129-bit arithmetic | 0.720 s | 0.635 s | 11.8% |
| Two-clock counters | 0.685 s | 0.600 s | 12.3% |
| UART pair | 4.129 s | 3.415 s | 17.3% |

Every paired run produced identical PASS/FAIL decisions, assertion counts,
elaborated interfaces, source hashes and **checked ZIP payload bytes**. Evidence
traces differ because optimized commands explicitly report reuse. This is a
selected four-input, one-host timing exercise with ordinary filesystem caches,
not general RTL performance, a human usability study or repair accuracy.

### What changed

Python 3.13's timed `Popen.wait` uses polling sleeps on POSIX. A single blocking
waiter thread now wakes the deadline-controlled caller when a process exits.
The original stdout file, process-group termination, CPU/address-space/file
limits and namespace environment are preserved. This mechanism's relative
benefit can differ on newer interpreters with native event-driven waiting.
[Python 3.13 subprocess reference](https://docs.python.org/3.13/library/subprocess.html#subprocess.Popen.wait)

Within **one checker call**, successful DUT preprocessing and initial base
elaboration can reuse an identical compiler result. Keys include all mounted
input bytes/paths, arguments, environment and compiler file identity. Reuse is
bounded to 16 entries / 32 MiB of output payload and never crosses original,
candidate or final checker calls. Sources using date/time preprocessor macros
bypass reuse. Failed results are never cached.

The frozen checker still validates source and output integrity on each test.
Every actual instantiated DUT configuration is elaborated fresh after the
bench is mounted. Test preprocessing, test compilation, nonce and simulation
are always fresh. Eight-profile application checks record 54 native commands
across discovery/final phases; actual launches change from 54 to 40 by reusing
14 identical preprocessing/base-elaboration operations. All eight tests remain.

The separately executed exported CI stays on the original uncached engine.
Its independent rebuild and older checked exports remain compatible. There is
no cache of a verification verdict or a model response, and no extra native
verification parallelism. Timeout and `$error`-then-completion controls still
fail. A launch-policy test compares the actual executable arguments, resource
limits, mounts, environment, stdin and process-session settings with reference.

## Docker code-only rebuild

Compiler/dependency installation now precedes application source copies. Changing
app code no longer invalidates the checksum-pinned Verilator installation layer.
Dependency definitions and compiler versions are unchanged.
[Docker cache rules](https://docs.docker.com/build/cache/invalidation/)

One paired code-only rebuild with local dependency caches available measured
**46.71 s → 5.02 s (9.3×)**. A harmless comment was changed in isolated contexts;
that comment is not published. The original Dockerfile reran compiler
installation; the reordered build reused that step. Initial setup still installs
the dependencies: this is not a cold-install, inference or hardware speed ratio.
Network/cache state can change rebuild timings.

## Reproduction and evidence

See `release/performance-v1.6.2.json` for plans, all paired observations, unchanged
payload digests and build-cache records. With a separate v1.6.1 source checkout:

```sh
python3 -I scripts/benchmark_project_latency.py --reference-source /path/to/v1.6.1 --output results/latency --trials 4
python3 -I scripts/benchmark_build_cache.py --reference-source /path/to/v1.6.1 --output /tmp/rtlrefine-build-test
python3 -m pytest -q tests/test_project_execution.py
```

All these checks make zero model requests. No original benchmark or experiment
record is rewritten. The older 15.0× historical candidate-screening result is a
different measurement and does not apply to this workflow.
