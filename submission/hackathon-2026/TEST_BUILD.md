# Run the test build

Download the complete versioned source:
https://github.com/ehdtjq08/RTLRefine/archive/refs/tags/v1.2.1.zip

Extract it and open a terminal in the extracted source directory. On a Linux
Docker host with the Compose plugin and unprivileged user namespaces enabled:

```sh
docker compose up --build
```

After the first build completes, open http://127.0.0.1:8501. No FPGA is required.
This upload-materials ZIP alone is not the complete application source.

The homepage lets you inspect recorded NVIDIA repairs and recheck their exact
source without a key. Open `/project` to upload the example ZIPs from this kit.
`wide-math-fixed.zip` should pass both benches. `wide-math-original.zip` should
fail its public bench. The intentionally incomplete `wide-math-partial.zip`
should pass the public bench and fail its audit. All three checks use zero model
requests; only the accepted source can be exported as a checked project.

Full judge instructions:
https://github.com/ehdtjq08/RTLRefine/blob/v1.2.1/docs/JUDGE_QUICKSTART.md

Project format and simulator limits:
https://github.com/ehdtjq08/RTLRefine/blob/v1.2.1/docs/USER_PROJECTS.md

New inference is disabled by default and requires an operator-supplied Nebius
credential. The public test build provides recorded model runs and fresh native
verification; it is not a public paid-inference endpoint.
