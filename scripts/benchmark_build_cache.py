"""Measure code-only rebuilds while preserving dependency/compiler versions."""
import argparse
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parent.parent
PROBE=b'\n# Build cache measurement only; this comment is not published.\n'


def context(reference,destination):
    destination.mkdir()
    required={'Dockerfile','.dockerignore'}
    for line in (reference/'Dockerfile').read_text().splitlines():
        if line.startswith('COPY '):
            words=shlex.split(line)[1:];words=[w for w in words if not w.startswith('--')];required.update(words[:-1])
    for name in sorted(required):
        source=reference/name;target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
        if source.is_dir():shutil.copytree(source,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.vvp','.git'))
        else:shutil.copy2(source,target)


def build(folder,tag,log):
    started=time.perf_counter()
    with log.open('wb') as out:
        subprocess.run(['docker','build','--progress=plain','-t',tag,'.'],cwd=folder,check=True,stdout=out,stderr=subprocess.STDOUT,timeout=1200)
    text=log.read_text()
    marker=next((re.match(r'#(\d+) ',line)[1] for line in text.splitlines() if 'RUN python /app/scripts/install_verilator_pinned.py' in line),None)
    cached=marker is not None and f'#{marker} CACHED' in text
    return {'seconds':time.perf_counter()-started,'compiler_install_step_cached':cached,'tag':tag}


def main():
    p=argparse.ArgumentParser();p.add_argument('--reference-source',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    reference=Path(a.reference_source).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
    left=out/'reference-context';right=out/'optimized-context';context(reference,left);context(reference,right)
    for name in ['Dockerfile','rtl_agent/project_repair/workflow.py','rtl_agent/project_repair/execution.py']:
        target=right/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    source=left/'rtl_app.py';source.write_bytes(source.read_bytes()+PROBE)
    baseline=build(left,'rtlrefine-build-reference-probe:1.6.2',out/'reference-rebuild.log')
    print(json.dumps({'reference_code_only_rebuild':baseline}),flush=True)
    warmup=build(right,'rtlrefine-performance:1.6.2',out/'optimized-first-build.log')
    source=right/'rtl_app.py';source.write_bytes(source.read_bytes()+PROBE)
    updated=build(right,'rtlrefine-build-optimized-probe:1.6.2',out/'optimized-rebuild.log')
    assert not baseline['compiler_install_step_cached'] and updated['compiler_install_step_cached']
    report={'status':'PASS','same_pinned_native_compiler_and_dependency_definitions':True,'new_model_calls':0,
            'reference_code_only_rebuild':baseline,'optimized_first_build':warmup,'optimized_code_only_rebuild':updated,
            'rebuild_ratio':baseline['seconds']/updated['seconds'],'probe_comment_not_in_published_source':True,
            'scope':'One paired code-only rebuild, local Docker cache available. Not cold first installation or model inference latency.'}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
