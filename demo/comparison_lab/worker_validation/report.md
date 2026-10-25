# Registered RTL comparison

**ADVANTAGE_NOT_ESTABLISHED**

Reasons: DEVELOPMENT_DATA, OUTCOMES_PREVIOUSLY_EXAMINED, RECORDED_REPLAY, SYSTEM_VALIDATION_FIXTURE, TOO_FEW_INDEPENDENT_PROJECTS, INCOMPLETE_PRIMARY_COMPARISON, NOT_BETTER_THAN_ALL_PRIMARY_BASELINES

Cohort: native_system_validation_only; 2 defect cases, 1 project groups, 1 trials/case.

Repeated trials are averaged within projects. Missing arms and uncovered defects remain visible.

| Method | Complete | Project-macro budget AUC | Accepted task-trials at max checks | API USD (attributed) |
|---|---|---:|---:|---:|
| source_order | True | 0.5000 | 1/2 | 0.00000 |
| size_order | True | 0.5000 | 1/2 | 0.00000 |
| heuristic_order | True | 0.2500 | 1/2 | 0.00000 |
| size_circuit_rrf | True | 0.4167 | 1/2 | 0.00000 |
| raw_single | False | — | 0/2 | 0.00000 |
| raw_consensus | False | — | 0/2 | 0.00000 |
| evidence_single | False | — | 0/2 | 0.00000 |
| evidence_ungated | False | — | 0/2 | 0.00000 |
| evidence_consensus | False | — | 0/2 | 0.00000 |
| without_dependency | True | 0.5000 | 1/2 | 0.00000 |
| without_scope | True | 0.2500 | 1/2 | 0.00000 |
| random_order | True | 0.5000 | 1/2 | 0.00000 |
| candidate | True | 0.2500 | 1/2 | 0.00000 |

## Full candidate-check budget curves

| Method | Pass@1 | Pass@2 | Pass@4 | Pass@8 |
|---|---:|---:|---:|---:|
| source_order | 0.500 | 0.500 | 0.500 | 0.500 |
| size_order | 0.500 | 0.500 | 0.500 | 0.500 |
| heuristic_order | 0.000 | 0.000 | 0.500 | 0.500 |
| size_circuit_rrf | 0.000 | 0.500 | 0.500 | 0.500 |
| raw_single | — | — | — | — |
| raw_consensus | — | — | — | — |
| evidence_single | — | — | — | — |
| evidence_ungated | — | — | — | — |
| evidence_consensus | — | — | — | — |
| without_dependency | 0.500 | 0.500 | 0.500 | 0.500 |
| without_scope | 0.000 | 0.000 | 0.500 | 0.500 |
| random_order | 0.500 | 0.500 | 0.500 | 0.500 |
| candidate | 0.000 | 0.000 | 0.500 | 0.500 |

## Registered paired comparisons

| Baseline | Effect | Simultaneous CI | Holm p | Pass |
|---|---:|---|---:|---|
| size_order | -0.2500 | [-0.25, -0.25] | 1.00000 | False |
| heuristic_order | 0.0000 | [0.0, 0.0] | 1.00000 | False |
| size_circuit_rrf | -0.1667 | [-0.16666666666666669, -0.16666666666666669] | 1.00000 | False |

Accounted API cost ceilings are secondary. Shared EDA timing is a replay attribution; no measured end-to-end speed or equal total-compute claim.

Project-cluster percentile intervals are approximate. Sign-flip inference assumes exchangeability. No repeated-trial pseudoreplication.

## Failure diagnosis at maximum checks

| Baseline | Treatment-only | Baseline-only | Tied | Missing |
|---|---:|---:|---:|---:|
| size_order | 0 | 0 | 2 | 0 |
| heuristic_order | 0 | 0 | 2 | 0 |
| size_circuit_rrf | 0 | 0 | 2 | 0 |
| raw_single | 0 | 0 | 0 | 2 |
| raw_consensus | 0 | 0 | 0 | 2 |
| evidence_consensus | 0 | 0 | 0 | 2 |

Candidate coverage: 1/2. Seeded-pool track: False. Uncovered cases stay in the denominator.
