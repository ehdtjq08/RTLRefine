# Registered RTL comparison

**ADVANTAGE_NOT_ESTABLISHED**

Reasons: DEVELOPMENT_DATA, OUTCOMES_PREVIOUSLY_EXAMINED, RECORDED_REPLAY, TOO_FEW_INDEPENDENT_PROJECTS, NOT_BETTER_THAN_ALL_PRIMARY_BASELINES

Cohort: historical_development; 9 defect cases, 2 project groups, 1 trials/case.

Repeated trials are averaged within projects. Missing arms and uncovered defects remain visible.

| Method | Complete | Project-macro budget AUC | Accepted task-trials at max checks | API USD (attributed) |
|---|---|---:|---:|---:|
| source_order | True | 0.1806 | 3/9 | 0.00000 |
| size_order | True | 0.0833 | 2/9 | 0.00000 |
| heuristic_order | True | 0.4028 | 4/9 | 0.00000 |
| size_circuit_rrf | True | 0.1111 | 2/9 | 0.00000 |
| raw_single | True | 0.2639 | 4/9 | 0.14510 |
| raw_consensus | True | 0.2917 | 4/9 | 0.43106 |
| evidence_single | True | 0.1806 | 3/9 | 0.22427 |
| evidence_ungated | True | 0.3472 | 4/9 | 0.68103 |
| evidence_consensus | True | 0.4028 | 4/9 | 0.68103 |
| without_dependency | True | 0.4583 | 5/9 | 0.00000 |
| without_scope | True | 0.4028 | 4/9 | 0.00000 |
| random_order | True | 0.4028 | 6/9 | 0.00000 |

## Full candidate-check budget curves

| Method | Pass@1 | Pass@2 | Pass@4 | Pass@8 |
|---|---:|---:|---:|---:|
| source_order | 0.111 | 0.222 | 0.222 | 0.333 |
| size_order | 0.000 | 0.000 | 0.222 | 0.222 |
| heuristic_order | 0.333 | 0.444 | 0.444 | 0.444 |
| size_circuit_rrf | 0.000 | 0.111 | 0.222 | 0.222 |
| raw_single | 0.111 | 0.222 | 0.222 | 0.444 |
| raw_consensus | 0.111 | 0.222 | 0.333 | 0.444 |
| evidence_single | 0.111 | 0.111 | 0.222 | 0.333 |
| evidence_ungated | 0.333 | 0.333 | 0.333 | 0.444 |
| evidence_consensus | 0.333 | 0.444 | 0.444 | 0.444 |
| without_dependency | 0.333 | 0.333 | 0.556 | 0.556 |
| without_scope | 0.333 | 0.444 | 0.444 | 0.444 |
| random_order | 0.000 | 0.222 | 0.444 | 0.667 |

## Registered paired comparisons

| Baseline | Effect | Simultaneous CI | Holm p | Pass |
|---|---:|---|---:|---|
| size_order | 0.3194 | [0.3055555555555556, 0.3333333333333333] | 1.00000 | False |
| heuristic_order | 0.0000 | [0.0, 0.0] | 1.00000 | False |
| size_circuit_rrf | 0.2917 | [0.24999999999999997, 0.3333333333333333] | 1.00000 | False |
| raw_single | 0.1389 | [0.0, 0.2777777777777778] | 1.00000 | False |
| raw_consensus | 0.1111 | [0.0, 0.2222222222222222] | 1.00000 | False |

Accounted API cost ceilings are secondary. Shared EDA timing is a replay attribution; no measured end-to-end speed or equal total-compute claim.

Project-cluster percentile intervals are approximate. Sign-flip inference assumes exchangeability. No repeated-trial pseudoreplication.

## Failure diagnosis at maximum checks

| Baseline | Treatment-only | Baseline-only | Tied | Missing |
|---|---:|---:|---:|---:|
| size_order | 3 | 1 | 5 | 0 |
| heuristic_order | 0 | 0 | 9 | 0 |
| size_circuit_rrf | 2 | 0 | 7 | 0 |
| raw_single | 1 | 1 | 7 | 0 |
| raw_consensus | 1 | 1 | 7 | 0 |

Candidate coverage: 8/9. Seeded-pool track: False. Uncovered cases stay in the denominator.
