# Evidence-grounded RTL candidate ranking

The `/ranking` page connects an observed output mismatch to the exact candidate
edit and a bounded original-netlist dependency range. NVIDIA ranks existing
content-addressed IDs. The controller attaches source facts and measures whether
the top-eight sets repeat across three shuffled menus. It uses the model order
only with at least two valid views and mean pairwise Jaccard overlap >= 0.35;
otherwise it uses the fixed circuit-evidence heuristic. Repeatability is not a
correctness probability, and the static cone is not dynamic causal proof.

Every method gets the same pool, an eight-candidate discovery budget and the
same first-public-pass stopping rule. A subsequent failed audit is terminal.
Model methods incur additional inference cost and latency. These are matched
candidate budgets, not equal end-to-end compute or speed measurements.

## Complete results

| Order | Historical development, 9 cases | New-module synthetic, 10 cases |
|---|---:|---:|
| Source position | 3 | 3 |
| Smallest edit | 2 | 7 |
| Fixed circuit-evidence heuristic | 4 | 6 |
| NVIDIA without evidence cards | 4, 5, 4 | 5 |
| NVIDIA with evidence cards, single view | 3, 4, 4 | 4 |
| Stability-gated NVIDIA + fixed heuristic | 4, 4, 4 | 7 |
| Exact uniform-random expected acceptances | 2.3881 | 3.3333 |

Each entry is the number of cases whose first discovery-passing selection also
passes both audit traces. Single-model format errors fall back to the fixed
heuristic. Three development trials reuse the same nine cases and do not make
27 independent defects. The cohorts and older experiments are not pooled.

The new-module result improves on the individual evidence and raw-model arms,
but **ties the smallest-edit baseline**. The development result ties the fixed
heuristic. These experiments do not establish superiority over the strongest
simple baseline, universal RTL performance, calibrated abstention or algorithmic
novelty. The performance claim remains limited to the table above.

In the synthetic cohort, model order is used for 2/10 cases; 8/10 fall back.
One admitted case adds an acceptance over the circuit heuristic; the other still
fails. In development, all 27 consensus decisions fall back. This is evidence
of a working gate, not evidence that repeatable model answers are reliable.

## Machine facts and model claims

`features.py` walks original Yosys output-bit drivers backwards, excluding clock
ports, bounded by 12 state edges and 80 cell edges. It records Yosys source
ranges, state/cell distance and the observed failing output/cycle. Ranges can
span an entire always block. The fixed score is:

`4 * dependency_relevance + 2 * related_site_fraction + 0.5 * edit_minimality + 2 * direct_target`

Related-site fraction compares same-family candidates with strict edit-set
supersets. It prefers structurally complete reset bundles but cannot establish
which sites semantically need modification. No corrected source or candidate
execution outcome is an input to these features or the model.

The model returns IDs and an explicitly unverified mechanism hypothesis. It
cannot author locations, dependencies, executable source, test results or
correctness probabilities. The operational service checks every candidate hash,
original span and reconstructed edit before ranking. Original public passes
skip ranking and paid calls. New model requests remain owner opt-in under the
persistent $50 total / $20 development budget guard.

## Development study and interface amendment

The existing finite grammar supplies 334 candidates for nine failing cases;
two original-passing reference controls bypass ranking. All 334 candidates are
labeled privately so uniform-random expectation is exact for these pools.
The original-input netlist and discovery observations, never candidate labels,
are used for planning. All plans finish before score analysis.

The initial strict interface required model-written source citations: 49/108
responses passed it; 59 failed (43 wrong citations, 3 incomplete responses and
13 invalid schemas). Before opening outcome labels, a separate amendment kept
only existing unique IDs in the first eight raw items and ignored model source
claims. No new inference was made. It is an amended interpretation, not an
interface prospectively registered before those calls. The original strict
scores remain in `demo/evidence_ranking/development/strict_scores`; the table
shows the amended ID-only scores. Original strict raw-model counts are 3, 5, 5;
its consensus counts remain 4, 4, 4.

108 calls cost an estimated $2.524932. All old V2 source/trace seals and the
preceding search results remain unchanged. The private catalog contains compile
failures and audit rejections; they are not removed from comparison pools.

## New-module synthetic ranking cohort

Four module paths were selected and the feature weights/gate frozen before
fetching their pinned contents. The operational ID-only interface was frozen
after fetch but before first source use. It was not tuned using the new-module
candidate outcomes.

| Module | Repository / pinned commit | Selected observable mutants |
|---|---|---:|
| `axis_rate_limit` | alexforencich/verilog-axis @ b9e0af36341a81ae80d6a8467b029d79c69b71cb | 3 |
| `axis_stat_counter` | same | 3 |
| `i2c_master` | alexforencich/verilog-i2c @ d8a7f9f972d9661b1cbd2e4db7b9f27407e84cb5 | 3 |
| `skidbuffer` | ZipCPU/wb2axip @ 8292c9e739fb57f3938aa7ae12693e20d1cbd9e4 | 1 |

A fixed-seed source-only operator replaces a same-width signal assignment RHS
with zero. The first three observable faults are retained per module, from at
most twelve available attempts. All **16 attempted mutations** are recorded;
10 were observable. Skidbuffer provides only one selected fault; no replacement
module or hand-picked extra mutation was added. Four normal source controls
pass replay unchanged.

Each pool contains 24 candidates: source-grammar distractors plus the known
inverse. **A solution is deliberately supplied.** This isolates ranking and
does not measure open-ended repair, grammar coverage or real historical bug
discovery. The original source and mutation labels are not in the model prompt.
These modules are new to this project's algorithm development, not guaranteed
absent from model training. Faults within a module are correlated.

The reference produces 256 public cycles and 512/768 audit cycles with separate
fixed seeds, repeated reset and valid-qualified payload observations. Source
fields are held under reference backpressure; concrete captured stimulus is
then replayed identically for every candidate. The I2C environment releases
external lines and feeds back the master's own open-drain drive: it covers
address/NACK/stop, without a responding slave or slave data transfers. The
inactive `FORMAL` appendix of skidbuffer is blanked without shifting lines.
These are two-state trace oracles from the original source, not independent
protocol proofs. Every seeded inverse passes all three profiles.

All 240 candidate labels are retained. One trial per case has one raw-model
view and three shuffled evidence views: **40 requests, estimated $0.678128**.
37 responses passed the ID schema; 3 invalid-ID responses fell back. All plans
were fixed before score analysis. No winner was used to change the algorithm.

## Run and inspect

```bash
python3 -m streamlit run rtl_app.py
# Open /ranking. Recorded browsing and replay require no API key.
```

Fresh checks additionally require Linux namespaces, Yosys, the pinned Verilator
4.038, g++, make, bubblewrap and prlimit. The page distinguishes recorded replay
from a fresh native compile/run, and exports hashed case evidence with licensing.

Replay the complete synthetic score calculation from the exported records:

```bash
python3 -m scripts.score_evidence_ranking \
  --inputs demo/evidence_ranking/holdout/inputs \
  --plans demo/evidence_ranking/holdout/plans \
  --catalog demo/evidence_ranking/holdout/catalog \
  --output results/replayed-ranking-score \
  --scope 'Synthetic ranking conditional on supplied known-positive pools'
```

The original results, raw responses, study controllers, freezes, all mutation
attempts and scores are retained in `demo/evidence_ranking`. Source licenses
remain MIT for the Alex Forencich modules, Apache 2.0 for skidbuffer, and the
existing MIT/GPL/BSD terms for the historical cohort. No physical board is used.
