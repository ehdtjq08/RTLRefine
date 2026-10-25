"""Run real supported repair workflows; NVIDIA use requires explicit --live."""
import argparse
import json

from rtl_agent.batch_repair.workflow import CASES,original,repair


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=tuple(CASES),default='overflow');parser.add_argument('--output',required=True);parser.add_argument('--live',action='store_true');args=parser.parse_args()
    result=repair(args.case,original(args.case),live=args.live,output=args.output,on_event=lambda e:print(e,flush=True))
    print(json.dumps({k:result.get(k) for k in ('status','accepted','pool_candidates','selected_id','api_requests','wall_seconds')},indent=2))


if __name__=='__main__':main()
