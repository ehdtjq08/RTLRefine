"""Paired project-level inference; repeated trials are averaged, not replicated."""
from __future__ import annotations

import itertools
import math
import random
import statistics


def holm(pvalues):
    ordered=sorted(pvalues,key=pvalues.get);m=len(ordered);running=0.;result={}
    for rank,key in enumerate(ordered):
        running=max(running,min(1.,(m-rank)*pvalues[key]));result[key]=running
    return result


def sign_flip(differences,*,seed=7703,samples=20000):
    """One-sided paired sign randomization, conditional on exchangeability.

    One value per independent project, never one per fault or model request.
    Exact for <=18 nonzero projects; Monte Carlo uses the plus-one correction.
    """
    values=[float(x) for x in differences if abs(x)>1e-14]
    observed=sum(values)
    if not values:return 1.
    if len(values)<=18:
        extreme=sum(sum(s*x for s,x in zip(signs,values))>=observed-1e-12
                    for signs in itertools.product((-1,1),repeat=len(values)))
        return extreme/(2**len(values))
    rng=random.Random(seed)
    extreme=sum(sum(rng.choice((-1,1))*x for x in values)>=observed-1e-12 for _ in range(samples))
    return (extreme+1)/(samples+1)


def quantile(values,p):
    if not values:raise ValueError('Empty sampling distribution')
    items=sorted(values);point=(len(items)-1)*p;left=int(point);right=min(left+1,len(items)-1)
    return items[left]*(right-point)+items[right]*(point-left) if right!=left else items[left]


def compare_projects(project_values,treatment,baselines,*,alpha=.05,resamples=5000,seed=1907,min_effect=.05,family_size=None):
    """Equal-project mean differences and Bonferroni percentile cluster CIs.

    The interval resamples paired project indices. Holm adjusts the primary
    one-sided tests. Few projects remain an explicit claim-gate failure.
    """
    groups=sorted(project_values);m=family_size or len(baselines);comparisons={}
    if m<len(baselines):raise ValueError('Correction family cannot shrink')
    if not groups:return {}
    for index,baseline in enumerate(baselines):
        diffs=[project_values[g][treatment]-project_values[g][baseline] for g in groups]
        rng=random.Random(seed) # identical project resamples across comparisons
        distribution=[statistics.mean(rng.choices(diffs,k=len(diffs))) for _ in range(resamples)]
        tail=alpha/(2*max(m,1))
        comparisons[baseline]={'effect':statistics.mean(diffs),'project_differences':dict(zip(groups,diffs)),
            'familywise_percentile_ci':[quantile(distribution,tail),quantile(distribution,1-tail)],
            'one_sided_sign_flip_p':sign_flip(diffs,seed=seed+index),
            'projects':len(groups),'min_practical_effect':min_effect,
            'assumptions':'Independent project clusters; paired method-label exchangeability under the null; bootstrap intervals are approximate.'}
    pvalues={k:v['one_sided_sign_flip_p'] for k,v in comparisons.items()}
    pvalues.update({f'__missing_{i}':1. for i in range(m-len(baselines))})
    adjusted=holm(pvalues)
    for key,value in comparisons.items():
        value['holm_p']=adjusted[key]
        value['passes_statistical_gate']=value['holm_p']<=alpha and value['familywise_percentile_ci'][0]>0 and value['effect']>=min_effect
    return comparisons


def minimum_discordant_projects(comparisons,alpha=.05):
    """Necessary best-case bound, not a power calculation or sufficient size."""
    return max(1,math.ceil(math.log2(max(comparisons,1)/alpha)))
