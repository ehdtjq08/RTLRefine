"""Freeze all inputs for new-module synthetic ranking before model access."""
import argparse
import json
from pathlib import Path

from rtl_agent.common import ROOT,new_run_dir,sha256,write_json
from rtl_agent.evidence_ranking.features import build_cards,heuristic_order,size_order
from rtl_agent.evidence_ranking.holdout_tools import (normalize_source,widths_from,mutation_options,
    candidate_pool,build_reference_traces,evaluate_source,SEED,POOL_CAP,PROFILES)
from rtl_agent.known_bugs_v2.engine import inspect
from rtl_agent.known_bugs_v2.evaluator import feedback
from rtl_agent.known_bugs_v2.runner import BenchmarkRunner


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    root=new_run_dir('synthetic_ranking_holdout',args.output);runner=BenchmarkRunner()
    ok,why=runner.probe(root/'isolation')
    if not ok:raise RuntimeError(why)
    sources=ROOT/'research/ranking_holdout'
    freeze=json.loads((sources/'ALGORITHM_FROZEN_BEFORE_SOURCE_USE.json').read_text())
    for n,h in freeze['files'].items():
        if sha256((ROOT/n).read_bytes())!=h:raise ValueError('Ranking policy changed after source-use freeze: '+n)
    write_json(root/'protocol.json',{'cohort':'New-module synthetic ranking, conditional on supplied pool containing a known inverse',
        'target_modules':4,'target_mutants_per_module':3,'max_attempts_per_module':12,'seed':SEED,'pool_cap':POOL_CAP,
        'profiles':PROFILES,'selection':'First three observable mutants in deterministic source-only order; no model outcomes used',
        'positive_seeded':True,'claims_excluded':['historical defect','grammar repair coverage','unseen model-training data','full protocol correctness'],
        'oracle':'Original-source two-state reference capture; valid-qualified payload, repeated resets, held source under backpressure',
        'i2c_scope':'Open-drain self-feedback with released external lines, address/NACK/stop only; no responding slave',
        'ranking_hashes':freeze['files'],'preparation_hash':sha256(Path(__file__).read_bytes()),
        'helpers_hash':sha256((ROOT/'rtl_agent/evidence_ranking/holdout_tools.py').read_bytes())})
    entries=[];attempts=[];modules=[]
    for module_entry in json.loads((sources/'SOURCES.json').read_text())['cases']:
        name=module_entry['id'];folder=root/name;folder.mkdir()
        raw=(sources/'sources'/name/'original.v').read_text()
        if sha256(raw.encode())!=module_entry['sha256']:raise ValueError('Pinned source changed')
        source,removed=normalize_source(raw);(folder/'reference.v').write_text(source)
        clock='i_clk' if name=='skidbuffer' else 'clk'
        ports=inspect(source,'',name,folder/'inspection',runner)
        interface=json.loads((folder/'inspection/interface.json').read_text())['modules'][name]
        widths=widths_from(interface)
        traces=build_reference_traces(source,ports,clock,name,folder,runner)
        case={'id':name,'top':name,'clock':clock,'ports':ports,'traces':traces}
        control=evaluate_source(source,source,case,folder/'normal_control',runner)
        if not control['accepted']:raise RuntimeError('Reference replay disagrees: '+name)
        selected=0
        for index,mutation in enumerate(mutation_options(source,widths),1):
            mutant=source[:mutation['start']]+'0'+source[mutation['end']:]
            attempt=folder/f'attempt_{index:02d}'
            result=evaluate_source(mutant,mutant,case,attempt,runner,discovery_only=True)
            observed=result['status']=='DISCOVERY_FAILED' and bool(result['traces'])
            attempts.append({'module':name,'attempt':index,'mutation':mutation,'observable':observed,'status':result['status']})
            write_json(root/'attempts.json',attempts)
            if not observed:continue
            selected+=1;opaque=f'holdout_{len(entries)+1:02d}';out=root/opaque;out.mkdir()
            (out/'input.v').write_text(mutant);(out/'dependencies.v').write_text('')
            (out/'candidate.v').write_text(mutant)
            (out/'inspect.ys').write_text(f'read_verilog -sv candidate.v\nhierarchy -check -top {name}\nproc\nflatten\nmemory_collect\nwrite_json flattened.json\n')
            cmd=runner.run('inspect',out,name)
            if cmd['status']!='PASS':raise RuntimeError('Mutant dependency extraction failed')
            netlist=json.loads((out/'flattened.json').read_text())['modules'][name]
            pool=candidate_pool(mutant,source,mutation,widths,ports)
            cards=build_cards(mutant,pool,netlist,result['traces'][0]['first_mismatches'])
            write_json(out/'pool.json',pool)
            write_json(out/'case.json',{**case,'id':opaque,'module_id':name})
            payload={'opaque_id':opaque,'case_id':opaque,'source_sha256':sha256(mutant.encode()),
                'original_discovery':feedback(result),'original_discovery_pass':False,'cards':cards,
                'source_order':[c['id'] for c in cards],'size_order':size_order(cards),'heuristic_order':heuristic_order(cards)}
            write_json(out/'rank_input.json',payload)
            entries.append({'opaque_id':opaque,'case_id':opaque,'module_id':name,'cards':len(cards),
                'rank_input_sha256':sha256((out/'rank_input.json').read_bytes()),'reference_sha256':sha256(source.encode())})
            print({'prepared':opaque,'module':name,'pool':len(cards)},flush=True)
            if selected==3:break
        modules.append({'module':name,'selected':selected,'formal_appendix_lines_blanked':removed,'normal_control_pass':True})
    write_json(root/'manifest.json',{'cases':entries,'modules':modules,'algorithm_hashes':freeze['files'],
        'scope':'New-module synthetic, known-positive candidate pools. All fault attempts retained; no candidate acceptance labels used for preparation.',
        'source_manifest_sha256':sha256((sources/'SOURCES.json').read_bytes())})
    write_json(root/'complete.json',{'status':'COMPLETE','cases':len(entries),'modules':len(modules),'new_model_calls':0})


if __name__=='__main__':main()
