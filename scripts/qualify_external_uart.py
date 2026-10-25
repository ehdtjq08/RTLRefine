"""Qualify historical source and maintainer control before any repair request."""
from __future__ import annotations

from rtl_agent.common import new_run_dir, sha256, write_json
from rtl_agent.uart_external.contract import DATA, VENDOR
from rtl_agent.uart_external.evaluator import evaluate, snapshot


def main():
    root = new_run_dir("external_uart_qualification")
    hashes = snapshot(root)
    results = {}
    print(str(root), flush=True)
    for label in ("buggy", "maintainer_fixed"):
        source = (VENDOR / label / "txuart.v").read_text()
        result = evaluate(source, root / label)
        results[label] = result
        print({"source": label, "status": result["status"], "sims": [r["passed"] for k in ("discovery_simulations", "audit_simulations") for r in result[k]],
               "formal": [r["status"] for r in result["formal"]]}, flush=True)
    buggy, fixed = results["buggy"], results["maintainer_fixed"]
    sims = buggy["discovery_simulations"] + buggy["audit_simulations"]
    qualified = (fixed["accepted"] and len(sims) == 12
                 and all(not r["passed"] if r["profile"]["flow_control"] else r["passed"] for r in sims)
                 and len(buggy["formal"]) == 2
                 and all(p["status"] == "COUNTEREXAMPLE" and p.get("replay", {}).get("status") == "CONTRACT_FAILURE_REPRODUCED" for p in buggy["formal"]))
    sealed = {str(p.relative_to(DATA)): sha256(p.read_bytes()) for p in sorted(DATA.iterdir()) if p.is_file()}
    record = {"qualified": qualified, "checker_hashes": hashes, "contract_hashes": sealed, "results": results,
              "historical_source_sha256": sha256((VENDOR / "buggy/txuart.v").read_bytes()),
              "maintainer_control_sha256": sha256((VENDOR / "maintainer_fixed/txuart.v").read_bytes()),
              "maintainer_used_only_as_pre_inference_control_not_runtime_scoring_or_model_context": True}
    write_json(root / "qualification.json", record)
    print({"qualified": qualified, "directory": str(root)}, flush=True)
    if not qualified:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
