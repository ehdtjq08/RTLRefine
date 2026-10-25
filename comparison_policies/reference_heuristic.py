"""Worker integration example. Identical to the existing baseline, not a new algorithm.

Implement rank(public, views, seed) with Python's standard library. The process
has no project filesystem, private labels, API key or network. Return existing
unique candidate IDs. A short list is completed with the fixed heuristic tail.
"""


def rank(public,views,seed):
    return public['orders']['heuristic_order']
