import argparse
import json
from pathlib import Path

from ..project_repair.project import load_project,read_archive,archive_project
from .contract import load_contract,bind_contract
from .examples import example_files
from .workflow import run_repair


def main():
    p=argparse.ArgumentParser(description='Find and repair failures missed by a FIFO smoke test')
    sub=p.add_subparsers(dest='command',required=True)
    sample=sub.add_parser('example');sample.add_argument('--kind',choices=('simultaneous','wrap','reset','healthy'),default='simultaneous');sample.add_argument('--output',required=True)
    for action in ('check','repair'):
        command=sub.add_parser(action);command.add_argument('--project',required=True);command.add_argument('--output',required=True)
    args=p.parse_args()
    if args.command=='example':Path(args.output).write_bytes(archive_project(load_project(example_files(args.kind))));return
    project=load_project(read_archive(Path(args.project).read_bytes()))
    result=run_repair(project,repair=args.command=='repair',output=args.output,on_event=lambda e:print(e['message'],flush=True))
    print(json.dumps({k:result.get(k) for k in ('status','accepted','api_requests','wall_seconds','error')},indent=2))


if __name__=='__main__':main()
