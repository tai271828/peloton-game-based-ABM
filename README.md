# proj-peloton-01 — Cycling peloton ABM (v0.5, "rigor release")

v0.5 adds **no new game mechanics**. It converts the v0.4 plug-and-play
framework into a report-ready model for a master's ABM course: **sensitivity
analysis** (Morris + Sobol + timestep robustness), **proper statistics**
(paired CIs, calibration holdout), **measured equilibria** (unilateral-
deviation / EGTA), **evolutionary dynamics**, an **ODD+ description**, and a
**pattern-oriented validation story** with an honest referent system
(criterium-scale racing).

**Read in order:**
1. [`context/task01-v0.5-discussion.md`](context/task01-v0.5-discussion.md) — why these items (the v0.4 review).
2. [`context/task02-v0.5-specification.md`](context/task02-v0.5-specification.md) — the build spec.
3. [`docs/odd-protocol.md`](docs/odd-protocol.md) — the model, ODD+ format.
4. [`docs/game-theory.md`](docs/game-theory.md) — the games, **including the v0.5 corrections**.
5. [`docs/validation.md`](docs/validation.md) — referent system + pattern battery.
6. [`summary.md`](summary.md) — results + improvements table.

## Headline results (all measured, not asserted)

| Result | Where |
|---|---|
| **The public-goods equilibrium is interior, not the corner.** Deviation payoffs are U-shaped (never pulling loses *position*); empirical Nash at **q\* ≈ 0.2**. The "Nash = everyone drafts" claim of v0.1–v0.4 was a 1-D artifact. | `figures/05` |
| **Evolution and best response agree.** 5 independent evolutionary runs converge to **p̂ = 0.19**; the measured best response at field 0.2 is **0.2**; deviations either way do worse. Two independent methods, one interior equilibrium. | `figures/06` |
| **The "hawk_dove" rules don't generate Hawk–Dove.** Measured best response *rises* with field aggression (strategic complementarity, escalation equilibrium ≈ 0.8) instead of falling (anti-coordination). Kept, renamed in claims, documented. | `figures/05c` |
| **Sensitivity:** aerobic power dominates pace, v_max dominates spread, draft geometry dominates sheltering; Sobol confirms with interaction structure; QoIs are insensitive to the timestep near the default. | `figures/07–09` |
| **Calibration survives holdout:** fit loss 0.570 vs holdout 0.580 (winner's-curse control), residual still localises the missing race-breaking mechanism. | `figures/03` |

## Quickstart

```bash
# env: uv-managed venv at the workspace root (course-abm/.venv); adds SALib
VIRTUAL_ENV="$(pwd)/.venv" uv pip install -r proj-peloton-01-v0.5-prototyping-fable/requirements.txt

cd proj-peloton-01-v0.5-prototyping-fable
PY=../.venv/bin/python

$PY -m pytest tests/ -q                       # 25 tests
$PY experiments.py                            # figures 01–06 (+ caches)
$PY -m peloton.analysis.sensitivity all --workers 7   # figures 07–09
$PY -m peloton.analysis.calibrate             # fit + holdout -> figures/03
$PY -m peloton.analysis.compare               # dashboard + paired contrasts
$PY -m peloton.viz.animate --strategy discrete_choice   # offline mp4
../.venv/bin/solara run peloton/viz/server.py # INTERACTIVE browser app
```

## Interactive visualization (Mesa 3 SolaraViz)

`peloton/viz/server.py` is the Mesa-3 equivalent of the course's Mesa-2
`server.py` (whose `ModularServer` API was removed in Mesa 3). Riders live in
a Mesa `ContinuousSpace` (their `(x, y)` on the stadium is synced every
step), so the space view uses Mesa's **built-in** space component — the track
outline is added via the `post_process` hook.

```bash
../.venv/bin/solara run peloton/viz/server.py   # http://localhost:8765
```

Controls: **game-theory dropdown** (every auto-discovered strategy — the
plug-and-play story as a live demo), rider/team sliders, play/step buttons,
live charts (mean speed, packs, finishers). Captains are stars; the rider in
the wind has a black edge; dropped riders grey out.

Note: agent `zorder` is pinned to 1 in the portrayal — Mesa 3.5.1's
`_scatter` has an operator-precedence bug that silently drops agents with
any other zorder (see comment in `server.py`). `viz/animate.py` is untouched
and remains the offline mp4 renderer.

## The v0.5 toolkit (on top of the v0.4 framework)

| tool | module | question it answers |
|---|---|---|
| comparison harness | `analysis/compare.py` | how do the games differ? (95 % CIs, paired contrasts) |
| deviation / EGTA | `analysis/deviation.py` | where are the equilibria, *measured*? |
| evolution | `analysis/evolution.py` | what do riders learn across races? is it stable? |
| Morris + Sobol + dt | `analysis/sensitivity.py` | which physics drives the behaviour? is dt safe? |
| calibration + holdout | `analysis/calibrate.py` | what do real-data targets imply about rider utilities? |
| batch runner | `analysis/batch.py` | thousands of races, all cores, deterministic |

Adding a game theory is still one file + one decorator
(`@register_strategy`); per-rider parameters (`strategy_params` as a list)
now support deviation experiments, evolutionary populations, and
heterogeneous fields.

## Layout

```
peloton/               framework core + strategies/ + analysis/ + viz/
context/               task01 discussion + task02 specification (this build's brief)
data/                  calibration targets + provenance + referent statement
docs/                  odd-protocol.md, game-theory.md, validation.md, specification.md
tests/                 24 fast tests
experiments.py         figures 01–06 + validation battery
figures/  summary.md
```
