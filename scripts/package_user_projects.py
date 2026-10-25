"""Package the independent user-project mode and authored example evidence."""
import json
import os
from pathlib import Path
import re
import shutil
import zipfile

from rtl_agent.common import ROOT,sha256,write_json
from rtl_agent.model_client import load_local_env


def main():
    demo=ROOT/'demo/user_projects';demo.mkdir(exist_ok=False)
    ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.vvp','*.lock')
    for run in ('project_wide_nebius_v1_20261024','project_dual_nebius_v1_20261024','project_wide_final_recheck_20261024','project_dual_final_recheck_20261024'):
        shutil.copytree(ROOT/'results'/run,demo/run,ignore=ignore)
    write_json(demo/'SCOPE.json',{'kind':'Authored importer/repair demonstrations, not unseen historical defect claims',
        'model_scope':'Actual design-only patches; original user benches unchanged; audit context withheld',
        'old_15x_speed_claim_applies':False})
    release=ROOT/'submission/user-projects-v1';release.mkdir(exist_ok=False);source=release/'source'
    shutil.copytree(ROOT/'submission/studio-v2/source',source)
    for name in ('rtl_app.py','project_app.py','rtl_agent/studio_ui.py','Dockerfile','.dockerignore','.streamlit/config.toml',
        'README.md','docs/USER_PROJECTS.md','tests/test_project_repair.py','scripts/check_project_import_browser.py','scripts/package_user_projects.py'):
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    for name in ('rtl_agent/project_repair','demo/user_projects'):shutil.copytree(ROOT/name,source/name,ignore=ignore)
    project=source/'pyproject.toml';project.write_text(re.sub(r'^version = "[^"]+"','version = "1.2.0"',project.read_text(),count=1,flags=re.M))
    load_local_env();secret=os.environ.get('NEBIUS_API_KEY','').encode();manifest={}
    for p in sorted(source.rglob('*')):
        if not p.is_file() or p==source/'manifest.json':continue
        name=p.relative_to(source);data=p.read_bytes()
        if any(part in ('.state','.env','.git','.tools','results') for part in name.parts):raise ValueError('Private workspace content in package')
        if secret and secret in data:raise ValueError('Provider credential in package')
        manifest[str(name)]={'sha256':sha256(data),'bytes':len(data)}
    write_json(source/'manifest.json',manifest);archive=release/'RTLRefine-user-projects-source.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(source.rglob('*')):
            if p.is_file():z.write(p,'RTLRefine/'+str(p.relative_to(source)))
    write_json(release/'SOURCE_PACKAGE.json',{'version':'1.2.0','files':len(manifest),'zip_bytes':archive.stat().st_size,
        'sha256':sha256(archive.read_bytes()),'credentials_included':False,'private_user_projects_included':False,
        'publicly_published':False,'scope':'User-supplied Verilog/SystemVerilog projects and immutable self-checking testbenches'})
    print({'files':len(manifest),'zip_bytes':archive.stat().st_size})


if __name__=='__main__':main()
