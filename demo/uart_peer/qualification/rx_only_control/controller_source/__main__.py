import argparse
import json
from pathlib import Path

from .project import read_archive,load_project
from .examples import example_zip
from .workflow import run_project


def main():
    p=argparse.ArgumentParser(description='Check and repair a submitted RTL project with its own testbenches')
    sub=p.add_subparsers(dest='command',required=True)
    example=sub.add_parser('example');example.add_argument('--kind',choices=('wide_math','dual_clock'),default='wide_math');example.add_argument('--output',required=True)
    for command in ('check','repair'):
        parser=sub.add_parser(command);parser.add_argument('--project',required=True);parser.add_argument('--output',required=True)
    args=p.parse_args()
    try:
        if args.command=='example':Path(args.output).write_bytes(example_zip(args.kind));print(args.output);return 0
        project=load_project(read_archive(Path(args.project).read_bytes()))
        result=run_project(project,repair=args.command=='repair',output=args.output,on_event=lambda e:print(e,flush=True))
        print(json.dumps({k:result.get(k) for k in ('status','accepted','api_requests','public_tests','audit_tests','ci_status','wall_seconds','error')},indent=2))
        return 0 if result['accepted'] else 1
    except (ValueError,RuntimeError,OSError,KeyError) as exc:
        print(json.dumps({'status':'SETUP_ERROR','accepted':False,'error':str(exc)},indent=2));return 2


if __name__=='__main__':raise SystemExit(main())
