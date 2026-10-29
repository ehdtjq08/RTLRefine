# Publication status

Source repository: https://github.com/ehdtjq08/RTLRefine

The repository contains source, licenses, setup instructions, current UI assets,
user-project examples and recorded verification evidence. Run the Docker test
build using the README. New model requests are disabled by default.

The current test build is v1.6.2, with first-use setup and result-display fixes.
The native checker, model case records and 2-minute-17-second video are unchanged.
[The automated workflow audit](FIRST_USE_AUDIT.md) is explicitly not an external
human user study. Current submission materials are in
[submission/uart-peer-v1](../submission/uart-peer-v1/README.md). They add the
historical UART peer case and a continuous normal-speed video showing fresh
checks, an actual recorded model result, exported CI and the separate FIFO
contract. Six actual UART requests and both failed runs are disclosed. The new
video still needs a public YouTube upload. No final Devpost submission by the
agent is claimed. See [the protocol and limits](UART_PEER_VALIDATION.md).

The earlier v1.5.0 submission materials are in
[submission/ci-v1](../submission/ci-v1/README.md), with general-project standalone
checking, JSON/JUnit and generated GitHub Actions workflows. The exact exported
runner is an additional acceptance gate. The repository's own CI reproduces
three checked/bug-reintroduced/restored cycles. Its live status is visible in
[GitHub Actions](https://github.com/ehdtjq08/RTLRefine/actions/workflows/general-project-ci.yml).
The current 2-minute-50-second video includes fresh CI export and needs a public
YouTube upload. Earlier v1.4.1 materials are in
[submission/external-v1](../submission/external-v1/README.md), with actual external
RTL validation added to the portable-regression, JSON-free setup and resource
diagnostic workflow. The earlier v1.4 materials remain in `submission/functional-v1`. The video
labels its actual recorded NVIDIA result and executes native checks fresh.
It still needs its own YouTube upload. Earlier v1.3.0 and v1.2.1 materials remain
in `submission/property-v1` and `submission/hackathon-2026`. The
[versioned test-build instructions](JUDGE_QUICKSTART.md) explain credential-free
native checking and the separately configured fresh-inference path.

Earlier project YouTube video: https://youtu.be/JEvktXDIUd0 . Its 106-second duration and
unauthenticated playback availability were checked. Visibility was Unlisted;
the owner should change it to Public before final submission. Current checks
are in [the publication receipt](../submission/hackathon-2026/PUBLICATION.json).

A separately hosted application has not been provided. No localhost address is
a public judging endpoint. Earlier publication flags inside experiment records
are historical snapshots; they are not rewritten.

The source was imported from the validated 1.2.0 package. Original dataset and
checker seals remain unchanged. Private keys, .env, personal spending state,
installed tool binaries and private user uploads are excluded.

The v1.6.2 performance patch preserves the frozen grader and standalone engine;
its timing and source-rebuild scope are documented in [PERFORMANCE.md](PERFORMANCE.md).
