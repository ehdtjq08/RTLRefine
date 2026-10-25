"""Export final comparison-system records; preserve original experiments."""
import argparse
from pathlib import Path
import shutil

from rtl_agent.common import ROOT,sha256,write_json


def main():
    p=argparse.ArgumentParser();p.add_argument('--runs',required=True);p.add_argument('--isolation-run',required=True);args=p.parse_args()
    out=ROOT/'demo/comparison_lab';out.mkdir(exist_ok=False)
    def copy(source,target):
        shutil.copytree(source,target,ignore=lambda path,names:[n for n in names if n in ('obj_dir','__pycache__') or n.endswith(('.pyc','.o','.a','.vvp','.lock'))])
    copy(Path(args.runs),out/'recorded_replay')
    copy(Path(args.isolation_run),out/'worker_validation')
    source=ROOT/'results/comparison_lab_native_smoke_v1_20261023'
    copy(source/'bundle',out/'native_fixture_bundle')
    copy(ROOT/'results/comparison_lab_native_fixture_20261023',out/'native_fixture_inputs')
    (out/'SCOPE.md').write_text('''# Comparison-system evidence

These records validate the comparison runner. All previous historical/synthetic
cases are exposed development data. The native counter cases and isolated policy
are authored integration fixtures, not NVIDIA performance or new real bug fixes.
Recorded inference replay makes no new paid call. Incomplete strong baselines
remain missing and block the final-advantage gate.

Original source/data licenses are retained in the surrounding project evidence.
The recorded_replay datasets include full editable source and source-edit spans;
full corresponding vendor sources, candidates and MIT/GPL/BSD license texts are
also retained in the earlier evidence directories. This export does not change
those frozen studies. Absolute paths in old protocols identify their original
run; use the documented replay command to produce a new portable run.
''')
    write_json(out/'MANIFEST.json',{str(f.relative_to(out)):sha256(f.read_bytes()) for f in sorted(out.rglob('*')) if f.is_file()})
    print({'export':str(out),'files':sum(f.is_file() for f in out.rglob('*'))})


if __name__=='__main__':main()
