import argparse
import json
from pathlib import Path

from ..project_repair.project import load_project,read_archive,archive_project
from .contract import load_contract,bind_contract
from .examples import example_files
from .workflow import run_repair
from .regressions import inherited_cases,check_bundle


def main():
    p=argparse.ArgumentParser(description='Find and repair failures missed by a FIFO smoke test')
    sub=p.add_subparsers(dest='command',required=True)
    sample=sub.add_parser('example');sample.add_argument('--kind',choices=('simultaneous','wrap','reset','healthy'),default='simultaneous');sample.add_argument('--output',required=True)
    for action in ('check','repair','regress'):
        command=sub.add_parser(action);command.add_argument('--project',required=True);command.add_argument('--output',required=True)
    args=p.parse_args()
    try:
        if args.command=='example':Path(args.output).write_bytes(archive_project(load_project(example_files(args.kind))));return 0
        project=load_project(read_archive(Path(args.project).read_bytes()))
        if args.command=='regress':
            if not inherited_cases(project,load_contract(project)):raise ValueError('This ZIP has no portable regressions; run a full FIFO check first')
            result=check_bundle(project,args.output)
        else:result=run_repair(project,repair=args.command=='repair',output=args.output,on_event=lambda e:print(e['message'],flush=True))
        print(json.dumps({k:result.get(k) for k in ('status','accepted','api_requests','new_model_calls','wall_seconds','error')},indent=2))
        return 0 if result['accepted'] else 1
    except (ValueError,RuntimeError,OSError,KeyError) as exc:
        print(json.dumps({'status':'SETUP_ERROR','accepted':False,'error':str(exc)},indent=2));return 2


if __name__=='__main__':raise SystemExit(main())
