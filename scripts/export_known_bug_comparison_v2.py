"""Export only a complete sealed cohort, keeping every failed request."""
import json
from pathlib import Path
import shutil

from rtl_agent.common import ROOT, sha256, write_json
from rtl_agent.known_bugs_v2.cases import DATA


def ignore(path, names):
    return [name for name in names if name in ("obj_dir", "__pycache__") or name.endswith((".pyc", ".o", ".a", ".vvp"))
            or name == "observed.hex" or (Path(path).name == "compiled" and name in ("stimulus.hex", "expected.hex"))]


def main():
    source = ROOT / "results/known_bug_paired_v2_20261023"
    summary = json.loads((source / "summary.json").read_text())
    if summary["status"] != "COMPLETE":
        raise ValueError("Do not publish an incomplete cohort as complete")
    destination = ROOT / "demo/known_bug_comparison_v2"
    destination.mkdir(exist_ok=False)
    shutil.copytree(source, destination / "run", ignore=ignore)
    frozen = json.loads((DATA / "FROZEN.json").read_text())
    qualification = Path(frozen["qualification"]).parent
    shutil.copytree(qualification, destination / "final_qualification", ignore=ignore)
    original_qual = json.loads((qualification / "qualification.json").read_text())["original_qualification"]
    shutil.copytree(Path(original_qual).parent, destination / "original_qualification", ignore=ignore)
    # Full corrected source is post-run audit/reproduction material, not loaded
    # by candidate admission or included in any model prompt.
    shutil.copytree(ROOT / "research/known_bug_benchmark/control_sources_v2", destination / "controls_after_inference")
    write_json(destination / "provenance.json", {"repository": "https://github.com/ekiwi/rtl-repair", "commit": "71e1afc0b9a2327d008b46acd415cf3f0343a938",
               "historical_research_artifact_versions": True, "not_claimed_untouched_upstream": True,
               "golden_trace_oracle": True, "reference_free_behavioral_proof": False,
               "new_discovery_or_unseen_accuracy": False, "all_failed_model_requests_retained": True,
               "original_excluded_scenarios": json.loads(Path(original_qual).read_text())["exclusions_before_inference"]})
    (destination / "MODIFICATIONS.md").write_text('''# Source and modification notices

The selected Verilog-axis files retain Alex Forencich's original MIT notices.
ZipCPU SPI files are copyright Gisselquist Technology, GPL-3.0-or-later.
Each sealed case carries the complete applicable license. Model-edited RTL
retains its vendor license and complete corresponding original/modified source.
The root MIT project license does not replace vendor licensing.

On 2026-10-23, NVIDIA Nemotron Ultra through Nebius Token Factory proposed the
recorded modifications. Raw JSON line edits are applied to the original input;
replacement blocks receive one final newline if missing, as declared before
inference. No functional controller/manual repair is inserted. Healthy controls
and every rejected, incomplete or audit-failing response remain in the record.
Public historical research-artifact versions can have appeared in training.
''')
    write_json(destination / "manifest.json", {str(p.relative_to(destination)): sha256(p.read_bytes()) for p in sorted(destination.rglob("*")) if p.is_file()})
    print(json.dumps({k: summary[k] for k in ("status", "totals", "paired_real_outcomes", "unique_paid_calls", "estimated_api_cost_usd")}, indent=2))


if __name__ == "__main__":
    main()
