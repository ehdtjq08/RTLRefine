"""Publish-ready local source package for the focused repair studio."""
import os
from pathlib import Path
import re
import shutil
import zipfile

from rtl_agent.common import ROOT,sha256,write_json
from rtl_agent.model_client import load_local_env


def main():
    release=ROOT/'submission/studio-v1';release.mkdir(exist_ok=True);source=release/'source'
    shutil.copytree(ROOT/'submission/comparison-lab-v1/source',source)
    files=['rtl_app.py','repair_studio_app.py','Dockerfile','.dockerignore','README.md','README.research.md',
        'docs/REPAIR_STUDIO.md','docs/DEPLOYMENT.md','tests/test_batch_repair.py',
        'scripts/install_verilator_pinned.py','scripts/probe_batch_repair.py','scripts/measure_batch_repair.py',
        'scripts/run_batch_repair_demo.py','scripts/export_repair_studio.py','scripts/check_repair_studio_browser.py',
        'scripts/record_repair_studio.py','scripts/package_repair_studio.py']
    for name in files:
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    for name in ('rtl_agent/batch_repair','demo/repair_studio'):
        shutil.copytree(ROOT/name,source/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.lock'))
    project=source/'pyproject.toml';project.write_text(re.sub(r'^version = "[^"]+"','version = "1.0.0"',project.read_text(),count=1,flags=re.M))
    load_local_env();secret=os.environ.get('NEBIUS_API_KEY','').encode();manifest={}
    for f in sorted(source.rglob('*')):
        if not f.is_file() or f==source/'manifest.json':continue
        name=f.relative_to(source);data=f.read_bytes()
        if any(part in ('.env','.state','.git','.tools','results') for part in name.parts):raise ValueError('Private/generated workspace root in package')
        if secret and secret in data:raise ValueError('Credential in package')
        manifest[str(name)]={'sha256':sha256(data),'bytes':len(data)}
    write_json(source/'manifest.json',manifest);archive=release/'RTLRefine-repair-studio-source.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(source.rglob('*')):
            if f.is_file():z.write(f,'RTLRefine/'+str(f.relative_to(source)))
    record={'version':'1.0.0','files':len(manifest),'zip_bytes':archive.stat().st_size,'sha256':sha256(archive.read_bytes()),
        'credentials_included':False,'publicly_published':False,'scope':'Guided finite-grammar repair, measured candidate-screening throughput and independent exact-source admission'}
    write_json(release/'SOURCE_PACKAGE.json',record);print(record)


if __name__=='__main__':main()
