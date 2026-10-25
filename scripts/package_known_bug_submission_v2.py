"""Standalone updated source and completed public-bug study, without secrets."""
from __future__ import annotations

import json
import os
import shutil
import zipfile

from rtl_agent.common import ROOT, sha256, write_json
from rtl_agent.model_client import load_local_env


def main():
    release = ROOT / "submission/known-bugs-v2"
    release.mkdir(exist_ok=True)
    destination = release / "source"
    shutil.copytree(ROOT / "submission/external-uart-v1/source", destination, dirs_exist_ok=True)
    files = ["rtl_app.py", "known_bugs_v2_app.py", "Dockerfile", ".dockerignore", "THIRD_PARTY_NOTICES.md",
             "docs/KNOWN_BUG_BENCHMARK_V2.md", "docs/RTL_AWARD_PLAN.md", "docs/DEPLOYMENT.md",
             "tests/test_known_bugs_v2.py", "tests/test_workspace_flow.py",
             "scripts/fetch_known_bug_artifact.py", "scripts/prepare_known_bug_benchmark_v2.py", "scripts/finalize_known_bug_dataset_v2.py",
             "scripts/run_known_bug_comparison_v2.py", "scripts/export_known_bug_comparison_v2.py", "scripts/check_known_bugs_v2_browser.py",
             "scripts/record_known_bugs_video_v2.py", "scripts/package_known_bug_submission_v2.py",
             "research/known_bug_benchmark/UPSTREAM_MANIFEST.json",
             "research/known_bug_benchmark/ARTIFACT_LICENSE.json",
             "research/known_bug_benchmark/ARTIFACT-LICENSE-BSD-3-Clause.txt"]
    for relative in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    ignore = lambda path, names: [n for n in names if n in ("obj_dir", "__pycache__") or n.endswith((".pyc", ".o", ".a", ".vvp"))]
    for relative in ("rtl_agent/known_bugs_v2", "external_cases/known_bugs_v2", "demo/known_bug_comparison_v2", "research/known_bug_benchmark/control_sources_v2", "research/known_bug_benchmark/v1_oracle_discrepancy"):
        shutil.copytree(ROOT / relative, destination / relative, ignore=ignore, dirs_exist_ok=True)
    readme = destination / "README.md"
    result=json.loads((ROOT/"demo/known_bug_comparison_v2/run/summary.json").read_text())
    totals=result["totals"]
    readme.write_text(f"""# RTLRefine: corrected known-bug evaluation V2

Run `python3 -m streamlit run rtl_app.py` and open `/benchmarks`.
The separately frozen V2 study uses nine historical defect versions and two
reference controls. Under valid-qualified golden-trace checks, self-review
passes {totals['self_review']['real_trace_passes']}/9 and execution feedback
passes {totals['checker_feedback']['real_trace_passes']}/9. There are
{result['unique_paid_calls']} actual requests, estimated ${result['estimated_api_cost_usd']:.6f}.
Each arm shares the first proposal and has at most two logical calls. One trial
per case cannot establish general/statistical superiority or semantic accuracy.

V1's normal-code-damage interpretation was withdrawn. Its TKEEP audit exceeded
the reference-supported input domain, and an NVIDIA popcount improvement was
wrongly rejected. V2 restricts masks to contiguous low-order ones, independently
checks frame-length expectations, masks invalid data and ignores SPI debug.
The exact V1 improvement must pass a regression test. Source edits alone are
not called harmful. The full superseded V1 source archive is retained under
`research/known_bug_benchmark/v1_oracle_discrepancy` for transparency.

This study uses golden traces from corrected research controls, with an
independent guard for frame-length expectations. It is not an unbounded or
reference-free proof, untouched upstream source, or unseen benchmark. Public
code may have appeared in training. Read `docs/KNOWN_BUG_BENCHMARK_V2.md`.

All failures, raw contexts/responses, line edits, sources, licenses and frozen
input/expected-output/checker hashes are included. No functional manual repair
is inserted. The source/data seals stayed unchanged during the V2 run. V1 and
all older experiments remain separate, without pooling success counts.

Fresh native checks require Linux namespaces, Yosys 0.51, Verilator 4.038, g++,
make, bubblewrap and prlimit. Browsing/checking make no paid call. Optional live
repair requires server opt-in and the persistent budget guard. The default
container browses recorded results and disables native checks without those
pinned tools. Other Icarus/Yosys workspaces remain available.

Project-authored code is MIT; vendor RTL retains MIT/GPL-3.0-or-later with full
corresponding source and notices. Provider keys, private budget state and tool
binaries are excluded. Public hosting, repository/YouTube publication, Devpost
submission and a human usability study are not claimed complete.

"""+readme.read_text().replace("# RTLRefine: verified external RTL repair","## Earlier external UART extension",1))
    project = destination / "pyproject.toml"
    project.write_text(project.read_text().replace('version = "0.4.0"', 'version = "0.6.0"'))
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
    archive = release / "RTLRefine-known-bugs-v2-source.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                output.write(path, "RTLRefine/" + str(path.relative_to(destination)))
    write_json(release / "SOURCE_PACKAGE.json", {"files": len(manifest), "bytes": archive.stat().st_size,
               "sha256": sha256(archive.read_bytes()), "credentials_included": False, "publicly_published": False})
    print({"files": len(manifest), "zip_bytes": archive.stat().st_size})


if __name__ == "__main__":
    main()
