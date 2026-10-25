"""Private complete candidate labels, never used as model inputs."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path

from rtl_agent.common import ROOT,new_run_dir,sha256,write_json
from rtl_agent.evidence_ranking.holdout_tools import evaluate_source
from rtl_agent.known_bugs_v2.runner import BenchmarkRunner


def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    inputs=Path(args.inputs).resolve();manifest=json.loads((inputs/'manifest.json').read_text())
    root=new_run_dir('private_synthetic_candidate_catalog',args.output)
    write_json(root/'protocol.json',{'inputs_sha256':sha256((inputs/'manifest.json').read_bytes()),
        'ranker_access':False,'scope':manifest['scope'],'script_sha256':sha256(Path(__file__).read_bytes())})
    def worker(entry):
        runner=BenchmarkRunner();folder=root/entry['opaque_id'];folder.mkdir()
        source=(inputs/entry['opaque_id']/'input.v').read_text()
        case=json.loads((inputs/entry['opaque_id']/'case.json').read_text())
        pool=json.loads((inputs/entry['opaque_id']/'pool.json').read_text())
        labels={}
        for i,candidate in enumerate(pool,1):
            result=evaluate_source(candidate['rtl'],source,case,folder/f'candidate_{i:03d}',runner)
            labels[candidate['rtl_sha256']]=result
            write_json(folder/'catalog.json',{'candidate_labels':labels})
        print({'complete_catalog':entry['opaque_id'],'candidates':len(labels)},flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(worker,e) for e in manifest['cases']]
        for f in as_completed(futures):f.result()
    write_json(root/'complete.json',{'status':'COMPLETE','cases':len(manifest['cases']),'new_model_calls':0})


if __name__=='__main__':main()
