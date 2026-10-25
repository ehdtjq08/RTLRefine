"""Package the experiment runner and reproducible records without credentials."""
import os
from pathlib import Path
import re
import shutil
import zipfile

from rtl_agent.common import ROOT,sha256,write_json
from rtl_agent.model_client import load_local_env


def main():
    release=ROOT/'submission/comparison-lab-v1';release.mkdir(exist_ok=False);source=release/'source'
    shutil.copytree(ROOT/'submission/ranking-v1-final/source',source)
    files=['README.md','docs/COMPARISON_LAB.md','configs/comparison_lab_final.json','tests/test_comparison_lab.py',
        'scripts/prepare_comparison_lab_smoke.py','scripts/export_comparison_lab.py','scripts/package_comparison_lab.py']
    for name in files:
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    for name in ('rtl_agent/comparison_lab','comparison_policies','demo/comparison_lab'):
        shutil.copytree(ROOT/name,source/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.lock'))
    project=source/'pyproject.toml';project.write_text(re.sub(r'^version = "[^"]+"','version = "0.9.0"',project.read_text(),count=1,flags=re.M))
    load_local_env();secret=os.environ.get('NEBIUS_API_KEY','').encode();manifest={}
    for f in sorted(source.rglob('*')):
        if not f.is_file() or f==source/'manifest.json':continue
        relative=f.relative_to(source);data=f.read_bytes()
        if any(part in ('.state','.env','.git','.tools','results') for part in relative.parts):raise ValueError('Private workspace root in package')
        if secret and secret in data:raise ValueError('Credential in package')
        manifest[str(relative)]={'sha256':sha256(data),'bytes':len(data)}
    write_json(source/'manifest.json',manifest);archive=release/'RTLRefine-comparison-system-source.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(source.rglob('*')):
            if f.is_file():z.write(f,'RTLRefine/'+str(f.relative_to(source)))
    record={'version':'0.9.0','files':len(manifest),'zip_bytes':archive.stat().st_size,'sha256':sha256(archive.read_bytes()),
        'credentials_included':False,'publicly_published':False,'new_model_calls_for_system_validation':0,
        'scope':'Comparison infrastructure; no new independent final-test superiority result claimed'}
    write_json(release/'SOURCE_PACKAGE.json',record);print(record)


if __name__=='__main__':main()
