# Current UART peer submission materials

Release v1.6.1 adds real historical UART peer validation and explicit rejected-
hypothesis/reasoning revision controls to the existing general-project CI flow.

- [Solo-entry About](DEVPOST_ABOUT.md)
- [Project fields and versioned test build](PROJECT_FIELDS.md)
- [Nebius/NVIDIA feedback](NEBIUS_FEEDBACK.md)
- [Latest normal-speed demo](video/RTLRefine-UART-peer-demo.mp4)
- [UART protocol and all failure disclosures](https://github.com/ehdtjq08/RTLRefine/blob/v1.6.1/docs/UART_PEER_VALIDATION.md)
- [Live hosted CI status](https://github.com/ehdtjq08/RTLRefine/actions/workflows/general-project-ci.yml)
- [Update guide](UPDATE_GUIDE_KO.md)

Six actual UART development requests are retained, including four requests in
failed runs. The final run used two requests and passed the fixed eight profiles
and exported CI. The checks were not weakened. Earlier materials remain in
submission/ci-v1 and other versioned folders.

This is known exposed historical behavior against an explicit peer contract,
not newly discovered defects, an introduced UART regression or unseen accuracy.
The new video still needs a public YouTube upload; the owner must update Devpost
and confirm final submission.

The v1.6.1 patch fixes first-use setup and stale-result handling. The video
remains the same v1.6.0 recording; native verification and cases are unchanged.
See [automated workflow audit](https://github.com/ehdtjq08/RTLRefine/blob/v1.6.1/docs/FIRST_USE_AUDIT.md).

The updated ready-to-copy bundle is [RTLRefine-first-use-submit-ready.zip](../RTLRefine-first-use-submit-ready.zip). The video is unchanged.
