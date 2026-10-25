"""Export a completed real external UART experiment, preserving failed calibration."""
import json
import shutil
from pathlib import Path

from rtl_agent.common import ROOT, sha256, write_json


def main():
    run = ROOT / "results/external_uart_final_v1_20261023"
    summary = json.loads((run / "summary.json").read_text())
    if summary["status"] != "COMPLETE":
        raise ValueError("Incomplete external UART experiment")
    destination = ROOT / "demo/external_uart"
    destination.mkdir(exist_ok=False)
    ignore = lambda path, names: [n for n in names if n == "__pycache__" or n.endswith((".pyc", ".vvp"))]
    shutil.copytree(run, destination / "run", ignore=ignore)
    shutil.copytree(Path(summary["qualification"]).resolve().parent, destination / "qualification", ignore=ignore)
    shutil.copytree(ROOT / "results/20261022T191745.414197Z_external_uart_qualification", destination / "initial_qualification", ignore=ignore)
    shutil.copytree(ROOT / "results/external_uart_compact_v1_20261023/checker_source", destination / "pre_boundary_checker_source", ignore=ignore)
    shutil.copytree(ROOT / "results/20261022T191331.444085Z_uart_external_calibration", destination / "excluded_mode_calibration", ignore=ignore)
    write_json(destination / "provenance.json", {"synthetic": False, "independent_original_author": "ZipCPU / Gisselquist Technology",
               "historical_not_new_discovery": True, "selected_case_not_held_out_accuracy": True,
               "training_contamination_cannot_be_excluded": True, "maintainer_source_is_pre_inference_control_only": True,
               "fixed_reference_rtl_used_for_scoring": False, "all_model_requests_and_failed_calibration_retained": True,
               "excluded_modes": "Divisor-two progress and computed-parity failures in maintainer control; excluded before model outcomes",
               "model_source_not_manually_edited": True, "upstream": json.loads((ROOT / "third_party/wbuart32_cts/source.json").read_text())})
    write_json(destination / "boundary_recheck.json", summary["posthoc_boundary_policy_fix"])
    (destination / "MODIFICATIONS.md").write_text('''# Modified UART source notice

The original txuart.v is copyright Gisselquist Technology and GPL-3.0-or-later.
On 2026-10-23, RTLRefine used NVIDIA Nemotron through Nebius Token Factory to
propose modified production RTL. All original license notices remain intact.
The complete corresponding original and modified source, raw responses, patches,
model context and GPL license accompany this evidence. This vendor-derived RTL
is distributed under GPL-3.0-or-later; the project's MIT license does not replace it.
The final checked source joins the model's exact body with unchanged original
interface/license prefix and disabled upstream formal appendix. No functional
manual repair is made. The controller boundary parser was corrected after the
fourth response; this post-hoc recheck and every failed request remain recorded.
''')
    write_json(destination / "manifest.json", {str(p.relative_to(destination)): sha256(p.read_bytes()) for p in sorted(destination.rglob("*")) if p.is_file()})
    print({k: summary[k] for k in ("accepted", "unique_paid_calls", "estimated_api_cost_usd")})


if __name__ == "__main__":
    main()
