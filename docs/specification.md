# Peloton ABM — v0.4 Specification (universal framework + data-facing game)

> Builds on v0.2 (plug-and-play actions/strategies on a stadium track) and
> v0.3 (team roles, lead-out game). v0.4 has two stated goals:
>
> 1. **A universal Mesa-based framework** where different game-theoretic
>    decision logics plug in trivially and their **emergent behaviours can be
>    compared easily**.
> 2. **A game theory that can interpret real-world competition data.**

`<project-root>` = `proj-peloton-01-v0.4-prototyping-fable/`.

---

## 1. Goal 1 — the universal framework

### 1.1 Plugin contract (tightened from v0.3)

A game theory is one class implementing `decide(SelfView, Perception) → Action`.
v0.4 removes the last bit of registration friction:

```python
# peloton/strategies/my_game.py   <- the WHOLE integration
from peloton.strategies.base import BaseStrategy, register_strategy

@register_strategy("my_game")
class MyGame(BaseStrategy):
    def decide(self, view, perc): ...
```

Modules in `peloton/strategies/` are **auto-discovered** at import; the
decorator registers the class; duplicate names raise immediately. Every CLI
(`compare`, `animate`) picks new strategies up automatically. v0.2/v0.3 still
required editing a registry dict; v0.4 requires editing **nothing**.

### 1.2 Comparison harness (new)

- `peloton/analysis/metrics.py` — every race is summarised by one **standard
  metric set** (speeds, finish stats, sheltered shares, per-action decision
  shares, winner profile), computed from cheap online per-agent counters — no
  DataFrame post-processing.
- `peloton/analysis/compare.py` — runs any list of registered games on
  **identical seeds** and emits a tidy DataFrame, a markdown table, and a
  dashboard figure (mean ± sd panels + action-mix fingerprint):

```bash
python -m peloton.analysis.compare                  # all registered games
python -m peloton.analysis.compare lead_out my_game --seeds 20
```

### 1.3 Shipped games

| name | family | from |
|---|---|---|
| `public_goods` | N-player prisoner's dilemma (pull vs draft) | v0.2 |
| `hawk_dove` | anti-coordination (contest for the wheel) | v0.2 |
| `lead_out` | altruistic team coordination with roles | v0.3, fixed in v0.4 |
| `discrete_choice` | **quantal response / logit (data-facing)** | **new** |
| `random` | null baseline (= `discrete_choice` at λ = 0) | new |

### 1.4 Acceptance criteria for goal 1

| # | Criterion | Where verified |
|---|---|---|
| A1 | New game = one file + one decorator, zero other edits | `tests/test_framework.py::test_plugin_registration_is_one_decorator` |
| A2 | All games comparable on identical seeds with one command | `python -m peloton.analysis.compare`, `figures/01_compare_all.png` |
| A3 | Standard metric schema independent of game | `peloton/analysis/metrics.py`, tests |
| A4 | Framework contract is executable (tests) | `tests/` — 18 tests, ~1 s |

---

## 2. Goal 2 — interpreting real competition data

### 2.1 The data-facing game: `discrete_choice`

Discrete-choice logit over the action vocabulary with interpretable weights
(`w_cost`, `w_shelter`, `w_position`) and rationality `λ` — i.e. **quantal
response** (McKelvey & Palfrey 1995), the standard empirical bridge between
game theory and observed behaviour. Two structural terms replace hard-coded
phases: the **shadow price of energy** (remaining distance) makes riders
empty the tank in the finale without a sprint rule, and **positional urgency**
(rising in progress) reproduces the finale positioning fight. Full math in
`docs/game-theory.md` §4; implementation in
`peloton/strategies/discrete_choice.py`.

### 2.2 The calibration pipeline

```
data/stylized_facts.csv  →  python -m peloton.analysis.calibrate
                         →  fitted weights + λ  (figures/03_calibration.json)
                         →  English interpretation + fit figure
```

- Targets: any observable from the standard metric set, with weights and
  documented sources (`data/README.md` — shipped values are **stylized
  facts**, explicitly user-replaceable).
- Fit: coarse grid + multiplicative local refinement on weighted relative
  squared error, seeds-averaged, in `collect=False` fast mode.
- Output: fitted parameters, per-observable before/after figure, and an
  auto-generated interpretation (energy-vs-position ratio, role of shelter,
  rationality regime).

### 2.3 Acceptance criteria for goal 2

| # | Criterion | Where verified |
|---|---|---|
| B1 | Strategy parameters are behaviourally interpretable | `discrete_choice.py` docstring, `calibrate.interpret()` |
| B2 | Pipeline fits sim observables to a data file | `figures/03_calibration.png/.json` |
| B3 | λ = 0 reproduces the null model exactly | rationality sweep, `figures/04_rationality_sweep.png` |
| B4 | Misfit is diagnosable, not hidden | drop-rate residual analysis (`docs/game-theory.md` §4.4) |

---

## 3. Framework changes from v0.3 (and why)

See `summary.md` for the full improvements table. Headlines:

1. **W′ fatigue speed cap** (`fatigue_knee`): below 25 % battery, max
   sustainable speed decays to the rider's aerobic speed. Physics fix for the
   v0.3 exploit (surging forever on an empty tank).
2. **Lead-out captain fix**: a captain no longer drafts a dying domestique
   into oblivion; if its wheel is slower than the local group it moves up.
   Together with (1) this **resolves the v0.3 known limitation** — organised
   teams now beat disorganised ones (mixed-field captain rank 0.06 vs 0.25;
   lead-out riders win 23/24 mixed races).
3. **O(n log n) perception** (sorted sliding window) and **online counters**
   → ~3× faster races and dataframe-free analysis; `collect=False` fast mode
   for calibration sweeps.
4. **Mesa `rng` migration** — no deprecation warnings; determinism tested.
5. **Test suite** (18 fast tests) — the plugin contract is executable.

## 4. Layout

```
peloton/                  the framework package
  actions.py  track.py  params.py  agent.py  model.py
  strategies/             auto-discovered plugins (base.py + 5 games)
  analysis/               metrics.py  compare.py  calibrate.py
  viz/animate.py          python -m peloton.viz.animate
data/                     stylized_facts.csv + provenance README
tests/                    pytest suite
experiments.py            figures 01/02/04 (03 via calibrate CLI)
figures/  docs/  README.md  summary.md  requirements.txt
```

Environment: launch-dir `.venv` (`course-abm/.venv`, uv-managed), as before.
