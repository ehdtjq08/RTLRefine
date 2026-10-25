"""Package the UI refresh over the frozen studio source, excluding credentials."""
import os
import re
import shutil
import zipfile

from rtl_agent.common import ROOT,sha256,write_json
from rtl_agent.model_client import load_local_env


def main():
    release=ROOT/'submission/studio-v2';release.mkdir(exist_ok=False);source=release/'source'
    shutil.copytree(ROOT/'submission/studio-v1/source',source)
    for relative in ('repair_studio_app.py','rtl_agent/studio_ui.py','rtl_agent/studio_theme.py','Dockerfile','.dockerignore',
        'README.md','THIRD_PARTY_NOTICES.md','docs/REPAIR_STUDIO.md','scripts/check_repair_studio_browser.py',
        'scripts/record_repair_studio.py','scripts/package_studio_design.py'):
        target=source/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/relative).read_bytes())
    shutil.copytree(ROOT/'assets',source/'assets')
    project=source/'pyproject.toml';project.write_text(re.sub(r'^version = "[^"]+"','version = "1.1.0"',project.read_text(),count=1,flags=re.M))
    load_local_env();secret=os.environ.get('NEBIUS_API_KEY','').encode();manifest={}
    for p in sorted(source.rglob('*')):
        if not p.is_file() or p==source/'manifest.json':continue
        relative=p.relative_to(source);data=p.read_bytes()
        if any(part in ('.env','.state','.git','.tools','results') for part in relative.parts):raise ValueError('Private workspace content in package')
        if secret and secret in data:raise ValueError('Provider credential in package')
        manifest[str(relative)]={'sha256':sha256(data),'bytes':len(data)}
    write_json(source/'manifest.json',manifest);archive=release/'RTLRefine-studio-design-source.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(source.rglob('*')):
            if p.is_file():z.write(p,'RTLRefine/'+str(p.relative_to(source)))
    write_json(release/'SOURCE_PACKAGE.json',{'version':'1.1.0','files':len(manifest),'zip_bytes':archive.stat().st_size,
        'sha256':sha256(archive.read_bytes()),'credentials_included':False,'publicly_published':False,
        'scope':'Repair studio visual refresh; backend and archived evidence unchanged',
        'previous_video':'The studio-v1 video documents the same workflow with the preceding UI'})
    print({'files':len(manifest),'zip_bytes':archive.stat().st_size})


if __name__=='__main__':main()
