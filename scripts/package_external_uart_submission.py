"""Standalone source/evidence release; previous submissions remain unchanged."""
from __future__ import annotations

import json
import os
import shutil
import zipfile

from rtl_agent.common import ROOT, sha256, write_json
from rtl_agent.model_client import load_local_env


def main():
    release = ROOT / "submission/external-uart-v1"
    release.mkdir(exist_ok=True)
    target = release / "source"
    shutil.copytree(ROOT / "submission/mutation-v1/source", target, dirs_exist_ok=True)
    files = ["rtl_app.py", "uart_app.py", "Dockerfile", ".dockerignore", "THIRD_PARTY_NOTICES.md",
             "docs/EXTERNAL_UART.md", "docs/DEPLOYMENT.md", "docs/RTL_AWARD_PLAN.md", "tests/test_external_uart.py", "tests/test_workspace_flow.py",
             "scripts/qualify_external_uart.py", "scripts/run_external_uart.py", "scripts/run_external_uart_recovery.py",
             "scripts/run_external_uart_compact_context.py", "scripts/recheck_external_uart_boundary.py", "scripts/export_external_uart.py",
             "scripts/check_external_uart_browser.py", "scripts/package_external_uart_submission.py"]
    for relative in files:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    ignore = lambda path, names: [n for n in names if n == "__pycache__" or n.endswith((".pyc", ".vvp"))]
    for relative in ("rtl_agent/uart_external", "external_cases/wbuart32_cts", "third_party/wbuart32_cts", "demo/external_uart"):
        shutil.copytree(ROOT / relative, target / relative, ignore=ignore, dirs_exist_ok=True)
    old = (target / "README.md").read_text()
    (target / "README.md").write_text('''# RTLRefine: verified external RTL repair

Run `python3 -m streamlit run rtl_app.py` and open `/uart` for the new external
historical case, or `/mutation` for the earlier synthetic queue experiment.

The external case is a real ZipCPU UART CTS/BREAK defect from another author
and project. A legal writer trusts a false not-busy signal and sends while the
receiver is blocking. Independent external-port/serial checks reproduce it.
No corrected UART RTL is used as the scoring oracle or given to NVIDIA.

All four paid development requests remain visible (estimated $0.174519). The
first incorrectly kept the broken source; the next two had output/patch failures.
The fourth exact model body passes 12 finite serial/flow checks and 80/96-step
CTS properties after an indentation-only controller boundary fix. The initial
parser rejection, exact parser diff and requalified original/maintainer controls
are retained. Simulation and formal checkers did not change. This post-hoc
recheck is not a prospectively frozen four-call success or a held-out accuracy
result. Small divisors and computed parity were excluded before inference after
maintainer-control calibration failures, also retained.

See `docs/EXTERNAL_UART.md`. Vendor and derived UART RTL are GPL-3.0-or-later,
with original notices, license, corresponding source and modification notice.
Project-authored Python remains under the root MIT license. A test build needs
Linux unprivileged namespaces; there is no unisolated RTL execution fallback.

The older synthetic results and negative 9-pair historical comparison remain
separate. Public hosting, repository publication, YouTube, Devpost submission and
human usability testing are not claimed complete. No key, private budget ledger
or installed tool binary is included in this source bundle.

''' + old.replace("# RTLRefine: specification-checked repair", "## Earlier synthetic challenge", 1))
    project = target / "pyproject.toml"
    project.write_text(project.read_text().replace('version = "0.3.0"', 'version = "0.4.0"'))
    load_local_env()
    secret = os.environ.get("NEBIUS_API_KEY", "").encode()
    manifest = {}
    for path in sorted(target.rglob("*")):
        if not path.is_file() or path == target / "manifest.json":
            continue
        relative = path.relative_to(target)
        content = path.read_bytes()
        if any(part in (".env", ".state", ".git", ".tools", "results") for part in relative.parts):
            raise ValueError("Private path in source release")
        if secret and secret in content:
            raise ValueError("Provider secret in release")
        manifest[str(relative)] = {"sha256": sha256(content), "bytes": len(content)}
    write_json(target / "manifest.json", manifest)
    archive = release / "RTLRefine-external-UART-source.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as out:
        for path in sorted(target.rglob("*")):
            if path.is_file():
                out.write(path, "RTLRefine/" + str(path.relative_to(target)))
    write_json(release / "SOURCE_PACKAGE.json", {"files": len(manifest), "zip_bytes": archive.stat().st_size,
               "sha256": sha256(archive.read_bytes()), "credentials_included": False, "publicly_published": False})
    print({"files": len(manifest), "zip_bytes": archive.stat().st_size})


if __name__ == "__main__":
    main()
