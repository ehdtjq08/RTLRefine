"""Publish a completed frozen synthetic cohort without rewriting any outcome."""
import json
import shutil

from rtl_agent.common import ROOT, sha256, write_json


def main():
    source = ROOT / "results/mutation_repair_v1_20261023"
    result = json.loads((source / "summary.json").read_text())
    if result["status"] != "COMPLETE":
        raise ValueError("Do not publish a partial repair cohort as complete")
    destination = ROOT / "demo/mutation_challenge"
    destination.mkdir(exist_ok=False)
    ignore = lambda path, names: [name for name in names if name == "__pycache__" or name.endswith((".pyc", ".vvp"))]
    shutil.copytree(source, destination / "run", ignore=ignore)
    shutil.copytree(ROOT / "results/20261022T180554.984958Z_mutation_qualification", destination / "qualification", ignore=ignore)
    shutil.copytree(ROOT / "research/mutation_challenge_v1_author", destination / "author_audit_after_inference")
    shutil.copytree(ROOT / "results/20261022T175526.151519Z_mutation_calibration", destination / "calibration_20step_unproven", ignore=ignore)
    write_json(destination / "provenance.json", {"constructed_faults": True, "not_real_defect_discovery": True,
               "all_cases_retained": True, "pristine_used_for_scoring": False,
               "author_audit_included_only_for_post_run_transparency": True,
               "dataset_scope": "Eight variants of one authored queue, six injected cases and two normal controls",
               "formal_scope": "2-word/16-step and 4-word/12-step two-state property checks with zero unspecified initial state; not unbounded",
               "calibration_note": "The earlier 4-word/20-step positive control timed out and remains UNPROVEN; final profiles were fixed before inference."})
    write_json(destination / "manifest.json", {str(p.relative_to(destination)): sha256(p.read_bytes()) for p in sorted(destination.rglob("*")) if p.is_file()})
    print({k: result[k] for k in ("accepted_repairs", "injected_cases", "controls_kept_unchanged", "normal_controls", "unique_paid_calls", "estimated_api_cost_usd")})


if __name__ == "__main__":
    main()
