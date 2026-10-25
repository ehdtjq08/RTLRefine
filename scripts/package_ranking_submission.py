"""Package current ranking source and full evidence, excluding local secrets."""
import argparse
import json
import os
import re
import shutil
import zipfile

from rtl_agent.common import ROOT,sha256,write_json
from rtl_agent.model_client import load_local_env


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='submission/ranking-v1-final');args=parser.parse_args()
    release=ROOT/args.output;release.mkdir(exist_ok=False)
    destination=release/'source'
    shutil.copytree(ROOT/'submission/search-v1/source',destination)
    files=['rtl_app.py','evidence_ranking_app.py','Dockerfile','.dockerignore','README.md','THIRD_PARTY_NOTICES.md','docs/EVIDENCE_RANKING.md',
        'tests/test_evidence_ranking.py','scripts/prepare_evidence_ranking.py','scripts/run_evidence_ranking_plans.py',
        'scripts/normalize_ranking_ids.py','scripts/build_candidate_catalog.py','scripts/score_evidence_ranking.py',
        'scripts/prepare_ranking_holdout.py','scripts/run_holdout_ranking_plans.py','scripts/build_holdout_catalog.py',
        'scripts/export_ranking_evidence.py','scripts/check_evidence_ranking_browser.py','scripts/package_ranking_submission.py']
    for relative in files:
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/relative).read_bytes())
    ignore=lambda path,names:[n for n in names if n in ('__pycache__','obj_dir') or n.endswith(('.pyc','.o','.a','.vvp'))]
    for relative in ('rtl_agent/evidence_ranking','demo/evidence_ranking','research/ranking_holdout'):
        shutil.copytree(ROOT/relative,destination/relative,ignore=ignore)
    project=destination/'pyproject.toml'
    project.write_text(re.sub(r'^version = "[^"]+"','version = "0.8.0"',project.read_text(),count=1,flags=re.M))
    load_local_env();secret=os.environ.get('NEBIUS_API_KEY','').encode();manifest={}
    for p in sorted(destination.rglob('*')):
        if not p.is_file() or p==destination/'manifest.json':continue
        relative=p.relative_to(destination);data=p.read_bytes()
        if any(n in ('.env','.state','.git','.tools','results') for n in relative.parts):raise ValueError('Private generated root in package')
        if secret and secret in data:raise ValueError('Provider credential in package')
        manifest[str(relative)]={'sha256':sha256(data),'bytes':len(data)}
    write_json(destination/'manifest.json',manifest)
    archive=release/'RTLRefine-evidence-ranking-source.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(destination.rglob('*')):
            if p.is_file():z.write(p,'RTLRefine/'+str(p.relative_to(destination)))
    record={'files':len(manifest),'zip_bytes':archive.stat().st_size,'sha256':sha256(archive.read_bytes()),
        'credentials_included':False,'publicly_published':False,'version':'0.8.0',
        'scope':'Ranking product and measured synthetic known-positive-pool evaluation; strongest simple baseline tied',
        'current_video_included':False,'prior_video_does_not_cover_this_new_ranking_study':True}
    write_json(release/'SOURCE_PACKAGE.json',record);print(record)


if __name__=='__main__':main()
