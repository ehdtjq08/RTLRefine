"""Export portable ranking inputs, fixed plans and complete measured outcomes."""
import json
from pathlib import Path
import shutil

from rtl_agent.common import ROOT,sha256,write_json

DEMO=ROOT/'demo/evidence_ranking'


def copy_tree(source,target,*,minimal_catalog=False):
    target.mkdir(parents=True,exist_ok=True)
    for p in sorted(source.rglob('*')):
        if not p.is_file() or 'obj_dir' in p.parts or (p.suffix not in ('.json','.v','.hex','.log','.py','.txt','.md') and p.name not in ('LICENSE','COPYING')):
            continue
        relative=p.relative_to(source)
        if minimal_catalog and not (p.name in ('catalog.json','complete.json','protocol.json') or p.name.startswith('trace_')):
            continue
        out=target/relative;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,out)


def main():
    if DEMO.exists():raise ValueError('Do not overwrite a prior evidence export')
    DEMO.mkdir(parents=True)
    cohorts={
        'development':{'inputs':'evidence_rank_inputs_v3_20261023','plans':'evidence_rank_ids_amended_v1_20261023',
            'raw_plans':'evidence_rank_plans_v1_20261023','catalog':'evidence_private_catalog_v1_20261023','scores':'evidence_rank_scores_ids_v1_20261023',
            'strict_scores':'evidence_rank_scores_strict_v1_20261023'},
        'holdout':{'inputs':'ranking_holdout_inputs_v1_20261023','plans':'ranking_holdout_plans_v1_20261023',
            'catalog':'ranking_holdout_catalog_v1_20261023','scores':'ranking_holdout_scores_v1_20261023'}}
    for name,parts in cohorts.items():
        for label,run in parts.items():
            copy_tree(ROOT/'results'/run,DEMO/name/label,minimal_catalog=label=='catalog')
    # The original development pools predate the new evidence features.
    copy_tree(ROOT/'results/repair_search_pools_v1_20261023',DEMO/'development/pools')
    copy_tree(ROOT/'research/ranking_holdout',DEMO/'source_provenance')
    write_json(DEMO/'COHORTS.json',{'cohorts':cohorts,'development_amendment':'ID-only interpretation recorded before opening outcome labels; original strict results retained',
        'holdout_scope':'New-module synthetic known-positive pools; algorithm frozen before source use, one trial with three menu permutations, not model-training holdout or historical bugs',
        'oracle_scope':'Fixed two-state golden trace agreement; first discovery pass chosen, audit passive; no retry after audit failure',
        'budget_scope':'Same eight candidate checks; model arms have unequal inference overhead and are not matched end-to-end compute',
        'licenses':'Source headers and per-project license texts retained. Skidbuffer Apache 2.0; Alex Forencich modules MIT; development corpus licenses in external_cases/known_bugs_v2.'})
    files={str(p.relative_to(DEMO)):{'sha256':sha256(p.read_bytes()),'bytes':p.stat().st_size} for p in DEMO.rglob('*') if p.is_file()}
    write_json(DEMO/'MANIFEST.json',files)
    print({'files':len(files),'bytes':sum(f['bytes'] for f in files.values())})


if __name__=='__main__':main()
