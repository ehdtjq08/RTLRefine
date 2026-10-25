"""Pre-inference cohort/controls/eligibility seal for the known-bug comparison."""
import argparse
import json
from pathlib import Path
import random
import shutil

from rtl_agent.common import ROOT, sha256, write_json
from rtl_agent.known_bugs_v2.cases import DATA
from rtl_agent.known_bugs_v2.evaluator import evaluate, snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qualification", required=True)
    args = parser.parse_args()
    report = json.loads(Path(args.qualification).read_text())
    eligible = report["qualified_cases"]
    if not 6 <= len(eligible) <= 10:
        raise ValueError("Prespecified cohort requires 6..10 qualified real defect cases")
    if (DATA / "FROZEN.json").exists():
        raise ValueError("Cohort already frozen")
    controls = []
    for parent in ("axis-frame-len-d13_d13", "zipcpu-spi-c1-c3-d9_c1"):
        if parent not in eligible:
            raise ValueError("Predesignated normal-control family did not qualify")
        identity = parent + "_normal"
        shutil.copytree(DATA / parent, DATA / identity)
        original = ROOT / "research/known_bug_benchmark/control_sources_v2" / (parent + ".v")
        source = original.read_text()
        (DATA / identity / "input.v").write_text(source)
        case = json.loads((DATA / identity / "case.json").read_text())
        case.update({"id": identity, "kind": "normal_control", "input_sha256": sha256(source.encode()), "parent_family": parent})
        write_json(DATA / identity / "case.json", case)
        controls.append(identity)
    # Verify admission, source policy and every audit oracle using the actual
    # final evaluator, before any model response is observed.
    root = ROOT / "results/known_bug_v2_final_qualification_20261023"
    root.mkdir(exist_ok=False)
    hashes = snapshot(root)
    rows = []
    for identity in eligible + controls:
        source = (DATA / identity / "input.v").read_text()
        result = evaluate(identity, source, root / identity)
        healthy = identity in controls
        if result["accepted"] != healthy or (not healthy and (not result["traces"] or result["discovery_pass"])):
            raise ValueError("Final evaluator disagrees with predeclared eligibility: " + identity + ": " + result["status"])
        rows.append({"id": identity, "kind": "normal_control" if healthy else "historical_defect", "evaluation": result})
        print({"case": identity, "status": result["status"], "expected_healthy": healthy}, flush=True)
    ids = eligible + controls
    random.Random(20261023).shuffle(ids)
    dataset = {"cases": [{"opaque_id": f"case_{i+1:02d}", "case_id": identity} for i, identity in enumerate(ids)],
               "real_cases": len(eligible), "normal_controls": len(controls), "qualification": str(root / "qualification.json")}
    write_json(root / "qualification.json", {"qualified": True, "cases": rows, "checker_hashes": hashes,
               "original_qualification": args.qualification, "cohort_selected_before_inference": True})
    write_json(DATA / "dataset.json", dataset)
    paths = [p for p in DATA.rglob("*") if p.is_file() and p.name != "FROZEN.json"]
    hashes_data = {str(p.relative_to(DATA)): sha256(p.read_bytes()) for p in sorted(paths)}
    write_json(DATA / "FROZEN.json", {"files": hashes_data, "checker_hashes": hashes,
               "qualification": str(root / "qualification.json"), "seed": 20261023,
               "scope": "Known public historical RTL defects, fixed-profile golden-trace regressions and pre-inference transformed audit traces. Training contamination possible; not a new discovery or independent behavioral proof."})
    print(json.dumps({"frozen": True, "real_cases": len(eligible), "normal_controls": len(controls)}, indent=2))


if __name__ == "__main__":
    main()
