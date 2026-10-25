"""Standalone updated source and completed public-bug study, without secrets."""
from __future__ import annotations

import json
import os
import shutil
import zipfile

from rtl_agent.common import ROOT, sha256, write_json
from rtl_agent.model_client import load_local_env


def main():
    release = ROOT / "submission/search-v1"
    release.mkdir(exist_ok=True)
    destination = release / "source"
    shutil.copytree(ROOT / "submission/known-bugs-v2/source", destination, dirs_exist_ok=True)
    files = ["rtl_app.py","repair_search_app.py","Dockerfile",".dockerignore","THIRD_PARTY_NOTICES.md",
             "docs/CONSTRAINED_REPAIR_SEARCH.md","docs/RTL_AWARD_PLAN.md","docs/DEPLOYMENT.md",
             "tests/test_constrained_search.py","tests/test_retention_generator.py","tests/test_search_study_control.py",
             "scripts/prepare_repair_search.py","scripts/run_repair_search_comparison.py","scripts/export_repair_search.py",
             "scripts/pilot_retention_search.py","scripts/check_repair_search_browser.py","scripts/package_repair_search.py",
             "scripts/record_repair_search_video.py"]
    for relative in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    ignore = lambda path, names: [n for n in names if n in ("obj_dir", "__pycache__") or n.endswith((".pyc", ".o", ".a", ".vvp"))]
    for relative in ("rtl_agent/repair_search","demo/repair_search"):
        shutil.copytree(ROOT/relative,destination/relative,ignore=ignore,dirs_exist_ok=True)
    readme=destination/"README.md"
    readme.write_text("""# RTLRefine: constrained search with NVIDIA ranking

Run `python3 -m streamlit run rtl_app.py`, then open `/search`.
Static search passes 3/9 known real scenarios and NVIDIA-prioritized search 4/9,
with the same original-only pool and cap of eight candidate checks per case.
Both reference controls pass unchanged by a common original-source gate.
NVIDIA only ranked IDs; all candidates were generated before inference.
Nine ranking requests cost an estimated $0.111220, excluding local compute.
All seals stayed unchanged. Logical checks were 49 versus 46; physical candidate
evaluations were cached across methods, so no end-to-end speedup is claimed.

This is a restricted lexical edit grammar with original-source Yosys widths,
not a general AST engine, SMT solver, new algorithm or unseen benchmark. Four
generated candidates failed compilation; all failures remain charged and recorded.
The one additional acceptance changes FIFO B only; the passing traces do not
establish the FIFO A path or all operating conditions. Both methods rejected a
partial reset edit that passed discovery and failed the two extra audits.
No audit observation or outcome controlled model ranking or another attempt.

The cohort follows V2 and a retention pilot, so it is development data. Its
compute budget differs from the older two-call V2 study; do not pool rates or
claim a matched improvement over that study. The one paired success difference
does not establish general or statistical superiority. See
`docs/CONSTRAINED_REPAIR_SEARCH.md` for methods, prior work and exact limits.

All plans, pools, failed sources, selected patches and original V2 oracles are
included. Vendor MIT/GPL and research BSD notices remain. Project-authored code
is MIT. Keys, private ledger, tool binaries and compiled model objects are absent.
Public repository, hosting, YouTube, Devpost and a human study remain pending.

"""+readme.read_text().replace("# RTLRefine: corrected known-bug evaluation V2","## Earlier separately frozen V2 study",1))
    project = destination / "pyproject.toml"
    project.write_text(project.read_text().replace('version = "0.6.0"', 'version = "0.7.0"'))
    load_local_env()
    secret = os.environ.get("NEBIUS_API_KEY", "").encode()
    manifest = {}
    for path in sorted(destination.rglob("*")):
        if not path.is_file() or path == destination / "manifest.json":
            continue
        relative = path.relative_to(destination)
        content = path.read_bytes()
        if any(part in (".env", ".state", ".git", ".tools", "results") for part in relative.parts):
            raise ValueError("Private/generated root in source package")
        if secret and secret in content:
            raise ValueError("Provider secret found in source package")
        manifest[str(relative)] = {"sha256": sha256(content), "bytes": len(content)}
    write_json(destination / "manifest.json", manifest)
    archive = release / "RTLRefine-search-source.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                output.write(path, "RTLRefine/" + str(path.relative_to(destination)))
    write_json(release / "SOURCE_PACKAGE.json", {"files": len(manifest), "bytes": archive.stat().st_size,
               "sha256": sha256(archive.read_bytes()), "credentials_included": False, "publicly_published": False})
    print({"files": len(manifest), "zip_bytes": archive.stat().st_size})


if __name__ == "__main__":
    main()
