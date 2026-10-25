# Registered RTL comparison

**ADVANTAGE_NOT_ESTABLISHED**

Reasons: DEVELOPMENT_DATA, OUTCOMES_PREVIOUSLY_EXAMINED, RECORDED_REPLAY, TOO_FEW_INDEPENDENT_PROJECTS, INCOMPLETE_PRIMARY_COMPARISON, NOT_BETTER_THAN_ALL_PRIMARY_BASELINES

Cohort: synthetic_seeded_development; 10 defect cases, 3 project groups, 1 trials/case.

Repeated trials are averaged within projects. Missing arms and uncovered defects remain visible.

| Method | Complete | Project-macro budget AUC | Accepted task-trials at max checks | API USD (attributed) |
|---|---|---:|---:|---:|
| source_order | True | 0.0370 | 3/10 | 0.00000 |
| size_order | True | 0.3519 | 7/10 | 0.00000 |
| heuristic_order | True | 0.3981 | 6/10 | 0.00000 |
| size_circuit_rrf | True | 0.3426 | 8/10 | 0.00000 |
| raw_single | True | 0.2037 | 5/10 | 0.12240 |
| raw_consensus | False | — | 0/10 | 0.00000 |
| evidence_single | True | 0.2963 | 4/10 | 0.18551 |
| evidence_ungated | True | 0.1481 | 3/10 | 0.55572 |
| evidence_consensus | True | 0.4537 | 7/10 | 0.55572 |
| without_dependency | True | 0.1667 | 5/10 | 0.00000 |
| without_scope | True | 0.3981 | 6/10 | 0.00000 |
| random_order | True | 0.0185 | 1/10 | 0.00000 |

## Full candidate-check budget curves

| Method | Pass@1 | Pass@2 | Pass@4 | Pass@8 |
|---|---:|---:|---:|---:|
| source_order | 0.000 | 0.000 | 0.000 | 0.300 |
| size_order | 0.200 | 0.300 | 0.300 | 0.700 |
| heuristic_order | 0.000 | 0.200 | 0.500 | 0.600 |
| size_circuit_rrf | 0.200 | 0.200 | 0.300 | 0.800 |
| raw_single | 0.200 | 0.200 | 0.200 | 0.500 |
| raw_consensus | — | — | — | — |
| evidence_single | 0.100 | 0.200 | 0.400 | 0.400 |
| evidence_ungated | 0.100 | 0.300 | 0.300 | 0.300 |
| evidence_consensus | 0.100 | 0.300 | 0.600 | 0.700 |
| without_dependency | 0.000 | 0.100 | 0.300 | 0.500 |
| without_scope | 0.000 | 0.200 | 0.500 | 0.600 |
| random_order | 0.000 | 0.000 | 0.000 | 0.100 |

## Registered paired comparisons

| Baseline | Effect | Simultaneous CI | Holm p | Pass |
|---|---:|---|---:|---|
| size_order | 0.1019 | [-0.22222222222222215, 0.33333333333333337] | 1.00000 | False |
| heuristic_order | 0.0556 | [0.0, 0.16666666666666669] | 1.00000 | False |
| size_circuit_rrf | 0.1111 | [-0.22222222222222215, 0.33333333333333337] | 1.00000 | False |
| raw_single | 0.2500 | [0.08333333333333337, 0.33333333333333337] | 0.62500 | False |

Accounted API cost ceilings are secondary. Shared EDA timing is a replay attribution; no measured end-to-end speed or equal total-compute claim.

Project-cluster percentile intervals are approximate. Sign-flip inference assumes exchangeability. No repeated-trial pseudoreplication.

## Failure diagnosis at maximum checks

| Baseline | Treatment-only | Baseline-only | Tied | Missing |
|---|---:|---:|---:|---:|
| size_order | 3 | 3 | 4 | 0 |
| heuristic_order | 1 | 0 | 9 | 0 |
| size_circuit_rrf | 0 | 1 | 9 | 0 |
| raw_single | 3 | 1 | 6 | 0 |
| raw_consensus | 0 | 0 | 0 | 10 |

Candidate coverage: 10/10. Seeded-pool track: True. Uncovered cases stay in the denominator.
