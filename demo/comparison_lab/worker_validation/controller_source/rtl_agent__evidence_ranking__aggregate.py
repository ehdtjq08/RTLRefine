"""Observable ranking stability and conservative fallback, not confidence scores."""
import itertools
import math

STABILITY_THRESHOLD=.35
CAP=8


def consensus(cards, views, threshold=STABILITY_THRESHOLD):
    from .features import heuristic_order
    fallback=heuristic_order(cards);valid=[v['ids'] for v in views if v['status']=='VALID']
    overlaps=[]
    for a,b in itertools.combinations(valid,2):
        aa,bb=set(a[:CAP]),set(b[:CAP]);overlaps.append(len(aa&bb)/len(aa|bb) if aa|bb else 1.)
    stability=sum(overlaps)/len(overlaps) if overlaps else 0.
    scores={i:0 for i in fallback};frequency={i:0 for i in fallback}
    for order in valid:
        for rank,identity in enumerate(order[:CAP]):scores[identity]+=CAP-rank;frequency[identity]+=1
    key={c['id']:c for c in cards}
    ranked=sorted(fallback,key=lambda i:(-scores[i],-key[i]['heuristic_score'],i))
    use_model=len(valid)>=2 and stability>=threshold
    return {'order':ranked if use_model else fallback,'raw_consensus_order':ranked,'used_model_order':use_model,
            'stability':stability,'stability_definition':'Mean pairwise top-eight Jaccard overlap; not correctness probability',
            'valid_views':len(valid),'topk_frequency':frequency,'borda_scores':scores,
            'fallback_reason':None if use_model else 'Insufficient valid or stable model views'}


def exact_random_baseline(outcomes, cap=CAP):
    """Uniform random order, stop at first discovery pass, audit passive."""
    n=len(outcomes);k=min(cap,n);good=sum(x['discovery_pass'] and x['accepted'] for x in outcomes)
    bad=sum(x['discovery_pass'] and not x['accepted'] for x in outcomes);m=good+bad
    def no_pass(t):
        return math.comb(n-m,t)/math.comb(n,t) if t<=n-m else 0.
    p_any=1-no_pass(k) if n else 0.
    return {'accepted_probability':p_any*good/m if m else 0.,'audit_rejection_probability':p_any*bad/m if m else 0.,
            'expected_candidate_checks':sum(no_pass(t) for t in range(k)) if n else 0.,
            'pool_size':n,'discovery_passes':m,'audit_passes':good,'cap':cap,'exact_conditional_on_scored_pool':True}


def poisson_binomial_tail(probabilities, observed):
    dist=[1.]
    for p in probabilities:
        nxt=[0.]*(len(dist)+1)
        for k,v in enumerate(dist):nxt[k]+=v*(1-p);nxt[k+1]+=v*p
        dist=nxt
    return sum(dist[observed:])
