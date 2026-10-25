# RTL comparison lab

This is an experiment runner for improving a ranking algorithm and testing a
frozen version against strong alternatives. It keeps public ranking inputs,
private native-check outcomes, registered policies and final reports separate.
It does not promise that the current algorithm will win.

## Run the completed development replay

```bash
python3 -m rtl_agent.comparison_lab replay-recorded \
  --output results/comparison_lab_replay
```

This imports all nine historical development defects and two normal controls,
then separately imports ten synthetic ranking tasks and four normal controls.
It makes **zero new API calls**. Both cohorts are marked previously examined.
The reports are `development_run/report.md` and `holdout_run/report.md` inside
the chosen output directory, with full JSON and hashed controller snapshots.
The word `holdout` here is an old directory name; these cases are now development
data and cannot be turned into fresh final-test evidence.

The expanded replay already finds a useful missing comparison: size/circuit
reciprocal-rank fusion passes 8/10 synthetic tasks at eight checks, while the
earlier gated policy passes 7/10. It also detects that this old cohort has only
one raw-model view per case, insufficient for a matched three-call baseline.
It reports that arm as unavailable and blocks an advantage claim. Source pools
without any passing candidate remain in the denominator: the historical pools
cover eight of the nine defects. No figure is substituted for a missing result.

## Replace the algorithm through a small interface

Put a Python file under `comparison_policies/` with:

```python
def rank(public, views, seed):
    # public contains original source, original discovery observations,
    # candidate evidence cards and the fixed baseline orders.
    # views contains only the model families declared when freezing.
    return public['orders']['heuristic_order']
```

The included `reference_heuristic.py` is an integration example, identical to
the existing baseline. It is not a new algorithm or a performance result.

```bash
python3 -m rtl_agent.comparison_lab import-recorded \
  --cohort development --output results/dev_bundle

python3 -m rtl_agent.comparison_lab freeze \
  --bundle results/dev_bundle --output results/my_policy_dev \
  --candidate comparison_policies/reference_heuristic.py \
  --candidate-views none

python3 -m rtl_agent.comparison_lab run --run results/my_policy_dev
```

The custom function runs in a fresh bubblewrap process with no network, API key,
project tree, private labels or shared memory from another case. Only the
standard Python runtime, the policy file and JSON inputs are provided. CPU,
memory, output size and runtime are bounded. Declared model inputs are `none`,
`raw`, `evidence` or `both`; their inference costs are attributed even when the
algorithm falls back. A returned short list receives the fixed heuristic tail.
Unknown or duplicate IDs are rejected. Policy errors retain a declared heuristic
fallback and an error record; no case is dropped.

Changing a policy requires a new frozen run. Existing completed reports and
controller snapshots are retained. Develop and choose variants on development
projects; the local exposure registry prevents a renamed dataset or GitHub URL
alias from turning an examined project into a fresh final-test project.

## Baselines and primary endpoint

Every run includes source order, smallest edit, fixed circuit evidence,
size/circuit reciprocal-rank fusion, and seeded random ordering. Model arms are
raw single-view, **raw three-view consensus**, evidence single-view, evidence
ungated consensus, and stability-gated evidence consensus. The raw/evidence
three-view arms use the same three menu permutations in a new live run. The
single-view arms reuse their first view with one-call cost attribution. Logical
arm costs and physical shared collection calls are different quantities.

The fixed circuit score is also ablated without its dependency term and without
its scope-completeness term. These are **static-score ablations**, not complete
ablation of everything an LLM could infer from the RTL.

The default primary endpoint is normalized trapezoid area under success versus
`log2(candidate-check budget)` at **1, 2, 4, 8** checks. All knots are fixed before
collection. A favorable eight-check result cannot replace this primary metric.
The first public-trace pass is selected, followed by two passive audit profiles;
an audit rejection never grants another candidate.

The default primary comparison family contains smallest edit, fixed circuit
evidence, their RRF combination, raw single-view and raw three-view consensus.
A new custom algorithm must also beat the previous gated policy. The report
keeps case-level wins/losses, failure transitions, generation coverage, healthy
controls, errors, API costs and ranking latency. It distinguishes pool misses,
ranking misses and public-pass/audit-rejection traps.

Candidate-check budgets are matched. Model costs and latency are additional.
The secondary API-cost-ceiling curves count a paid fallback as paid. Shared
native records permit serial tool-time attribution; this is a replay estimate,
not independent end-to-end speed measurement or an equal-total-compute claim.

## Prepare native data without planting a solution

`native-prepare` accepts a JSON manifest with cohort/exposure/oracle scope and
case descriptors. Each descriptor names an upstream project, defect/control
kind, editable source, optional read-only dependencies, top module, clock and
three trace profiles. Each profile declares hex stimulus/expected files,
cycles, input/output column names and label. All paths are relative to the
manifest directory; case paths cannot escape it. Keep the original source
license and upstream commit in the supplied case files/provenance.

The included smoke recipe is a complete format example:

```bash
python3 -m scripts.prepare_comparison_lab_smoke --output results/native_inputs
python3 -m rtl_agent.comparison_lab native-prepare \
  --manifest results/native_inputs/cases.json --output results/native_bundle
```

It runs the pinned Yosys/Verilator checker in isolation, generates the finite
source-only grammar from original widths, then labels **every candidate**.
It never reads a corrected source to insert a known inverse. The generated
bundle contains separate public/private files and a content seal. Unsupported,
empty-pool and unrepairable cases remain visible, rather than being replaced
with easier examples. Mixed historical/synthetic defect cohorts are rejected.
Explicitly seeded pools are restricted to a conditional-ranking claim.

The smoke cases use an independent Python counter recurrence: one repairable
retention fault, one arithmetic fault outside this grammar, and one normal
control. Native checks find one accepted candidate in the first pool, none in
the second, and all normal profiles pass. These cases validate the runner;
their metadata blocks any AI-performance claim.

Fresh native preparation requires Linux user/network/filesystem namespaces,
Yosys, Verilator **4.038**, g++, make, bubblewrap and prlimit. The current harness
is for one declared clock and public input/output ports <=64 bits at pinned
configurations. A trace oracle establishes only its declared input profiles;
it is not an unbounded correctness proof.

## Register a final study before preparing its data

The final-test path requires a new-project manifest and freezes the policy,
checker, model configuration, baselines and statistical settings **before any
RTL/trace content is read by native preparation**. Registration reads the
manifest and development-project metadata only. This is an auditable local
workflow, not a claim of cryptographic protection against a dishonest operator.

```bash
python3 -m rtl_agent.comparison_lab register-study \
  --manifest eval_cases/cases.json --output studies/final.json \
  --development-bundle results/dev_bundle \
  --candidate comparison_policies/my_algorithm.py --candidate-views evidence \
  --trials 3 --config configs/comparison_lab_final.json

python3 -m rtl_agent.comparison_lab native-prepare \
  --manifest eval_cases/cases.json --study studies/final.json \
  --output results/final_data

python3 -m rtl_agent.comparison_lab freeze \
  --bundle results/final_data/bundle --output results/final_study \
  --mode confirmatory --provider live --trials 3 \
  --development-bundle results/dev_bundle \
  --candidate comparison_policies/my_algorithm.py --candidate-views evidence \
  --config configs/comparison_lab_final.json

python3 -m rtl_agent.comparison_lab run --run results/final_study
```

The last command makes paid Nebius requests. The sample config caps that run
at $8; the persistent $50 total / $20 development guard still applies. Collection
stops incomplete when another conservative reservation does not fit. Each
failing nonempty case uses six physical calls per trial: three raw and three
evidence views. Original-passing controls and empty pools use no inference.

Default admission requires **at least eight independent defect projects**,
three trials/case, no development-project overlap and unexamined outcomes.
Eight is an operational floor, not a power guarantee. Public code is not
guaranteed absent from model training. Projects with shared derivation must be
assigned to the same project group. Equal source text cannot count as separate
projects. Healthy-control-only projects cannot inflate the defect sample size.

The final settings must match the pre-preparation registration. All algorithm,
prompt/client, checker and configuration hashes must remain unchanged.
Completed plans are sealed before private outcome decoding. Opening outcomes
records their project exposure; changing a seed, renaming the bundle or editing
the policy cannot silently create another fresh test.

## Statistical decision and recovery

Trials and faults are averaged within upstream project groups. Project means
receive equal weight. The evaluator uses paired project-level sign flips and
paired project bootstrap intervals, with Holm correction for the **entire
registered comparison family**, including missing arms. Bootstrap intervals use
a Bonferroni familywise percentile tail; they are approximate, especially with
few projects. Sign-flip inference requires project independence and paired-label
exchangeability under the null. See the primary
[SciPy paired permutation documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html),
[paired bootstrap documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html),
and [Holm correction documentation](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html).

`ADVANTAGE_ESTABLISHED_FOR_REGISTERED_SCOPE` requires a complete prospective
final run and improvement against **every** primary baseline: positive adjusted
interval lower bound, Holm p <= 0.05 and the registered practical effect (default
0.05 normalized AUC). Otherwise the report says `ADVANTAGE_NOT_ESTABLISHED` with
specific reasons. A seeded-pool study can establish only conditional ranking
performance; a finite-grammar study is limited to that generator and those
profiles. Neither status establishes universal RTL superiority or novelty.

Each view is checkpointed before the next starts. Saved responses are parsed
without reissuing the request. A pending request whose completion is uncertain
is blocked rather than automatically repeated. Resume an unchanged run with
the same `collect`/`run` command. Budget, code/data hash changes, missing plans,
changed reports or another active process produce explicit failures. Known
pipeline interruptions never authorize silent case deletion or selective retry.
