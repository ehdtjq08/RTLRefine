"""Run with python -m rtl_agent.comparison_lab; paid collection is explicit."""
import argparse
import json
from pathlib import Path

from .import_recorded import import_cohort
from .protocol import freeze,register_study
from .collect import collect
from .analyze import analyze
from .data import create_bundle


def main():
    parser=argparse.ArgumentParser(description='Frozen RTL ranking comparison, project-level analysis and claim gate')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('import-recorded');p.add_argument('--cohort',choices=('development','holdout'),required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('bundle');p.add_argument('--public',required=True);p.add_argument('--private',required=True);p.add_argument('--metadata',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('native-prepare');p.add_argument('--manifest',required=True);p.add_argument('--output',required=True);p.add_argument('--study')
    p=sub.add_parser('register-study');p.add_argument('--manifest',required=True);p.add_argument('--output',required=True);p.add_argument('--development-bundle',required=True);p.add_argument('--trials',type=int,default=3);p.add_argument('--candidate');p.add_argument('--candidate-views',choices=('none','raw','evidence','both'),default='evidence');p.add_argument('--config')
    p=sub.add_parser('freeze');p.add_argument('--bundle',required=True);p.add_argument('--output',required=True);p.add_argument('--mode',choices=('development','confirmatory'),default='development');p.add_argument('--provider',choices=('recorded','live'),default='recorded');p.add_argument('--trials',type=int,default=1);p.add_argument('--development-bundle');p.add_argument('--config');p.add_argument('--candidate');p.add_argument('--candidate-views',choices=('none','raw','evidence','both'),default='evidence')
    for command in ('collect','analyze','run'):
        p=sub.add_parser(command);p.add_argument('--run',required=True)
    p=sub.add_parser('replay-recorded');p.add_argument('--output',required=True)
    args=parser.parse_args()
    if args.command=='import-recorded':print(import_cohort(args.cohort,args.output));return
    if args.command=='bundle':
        print(create_bundle(args.output,json.loads(Path(args.public).read_text()),json.loads(Path(args.private).read_text()),json.loads(Path(args.metadata).read_text())));return
    if args.command=='native-prepare':
        from .native import prepare
        print(prepare(args.manifest,args.output,study=args.study));return
    if args.command=='register-study':
        result=register_study(args.manifest,args.output,development_bundle=args.development_bundle,trials=args.trials,
            candidate=args.candidate,candidate_views=args.candidate_views,overrides=json.loads(Path(args.config).read_text()) if args.config else None)
        print(json.dumps({'status':'REGISTERED_BEFORE_SOURCE_PREPARATION','projects':result['projects']}));return
    if args.command=='freeze':
        result=freeze(args.bundle,args.output,mode=args.mode,provider=args.provider,trials=args.trials,development_bundle=args.development_bundle,
            overrides=json.loads(Path(args.config).read_text()) if args.config else None,candidate=args.candidate,candidate_views=args.candidate_views)
        print(json.dumps({'status':'FROZEN','mode':result['mode'],'project_groups':result['project_groups']}));return
    if args.command=='collect':print(json.dumps(collect(args.run)));return
    if args.command=='analyze':result=analyze(args.run)
    elif args.command=='run':collect(args.run);result=analyze(args.run)
    else:
        root=Path(args.output);root.mkdir(parents=True,exist_ok=False);out={}
        for cohort in ('development','holdout'):
            bundle=import_cohort(cohort,root/(cohort+'_dataset'));run=root/(cohort+'_run')
            freeze(bundle,run);collect(run);report=analyze(run)
            out[cohort]={'decision':report['decision'],'report':str(run/'report.md')}
        print(json.dumps(out,indent=2));return
    print(json.dumps({'decision':result['decision'],'defect_cases':result['defect_cases'],'independent_projects':result['independent_project_groups']},indent=2))


if __name__=='__main__':main()
