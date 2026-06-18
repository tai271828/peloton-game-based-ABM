# Summary — Peloton ABM v0.5 ("rigor release")

Built from [`context/task01-v0.5-discussion.md`](context/task01-v0.5-discussion.md)
(the v0.4 review) via [`context/task02-v0.5-specification.md`](context/task02-v0.5-specification.md).
No new game mechanics — v0.5 makes the model *defensible*: SA, statistics,
measured equilibria, evolution, ODD+, and an honest validation story.

## Spec acceptance — status

| item | criterion | status |
|---|---|---|
| SA | Morris (r=20, 660 races) + Sobol (top-6, 3072 races) + dt robustness | ✅ figs 07–09 |
| ST | paired 95 % CI contrasts in compare; calibration holdout | ✅ `*_paired.md`, fig 03 |
| EQ | deviation payoffs locate equilibria for both stylised games | ✅ fig 05 |
| EV | evolution on current physics + stability cross-check | ✅ fig 06 |
| OD | ODD+ document | ✅ `docs/odd-protocol.md` |
| VA | crit referent + pattern battery + explicit de-scopes | ✅ `docs/validation.md` |

## Scientific headlines

1. **The interior equilibrium, triangulated.** The unilateral-deviation
   harness shows public-goods deviation payoffs are **U-shaped**: a rider who
   never pulls saves energy but surrenders *position* and loses the sprint
   from the back. Empirical Nash at **q\* ≈ 0.2** (fig 05b). Independently,
   five evolutionary runs converge to **p̂ = 0.19** and deviations around it
   do strictly worse (fig 06). Equilibrium ≪ social optimum, so the social
   dilemma survives — but the v0.1–v0.4 claim "Nash = everyone drafts" is
   **corrected**: it was an artifact of 1-D physics with no within-pack
   position.
2. **The "hawk_dove" rules do not generate Hawk–Dove.** Measured best
   response *rises* with field aggression — strategic complementarity with an
   escalation equilibrium ≈ 0.8 (fig 05c), not anti-coordination. Documented
   as a designed-game vs measured-game lesson (`docs/game-theory.md` §2).
3. **Sensitivity:** `aer_power` dominates pace, `v_max` dominates spread,
   draft geometry (`draft_gap_m`) dominates sheltering (Morris, fig 07;
   Sobol confirms with first-order vs total indices, fig 08). `fatigue_knee`
   is *low*-influence on aggregate QoIs — the W′ cap fixes the v0.3 exploit
   without becoming a fragile driver. QoIs are stable in `dt` near the
   default (fig 09).
4. **Calibration survives its holdout** (winner's-curse control): fit loss
   0.570 vs holdout 0.580. The drop-rate residual still correctly localises
   the missing race-breaking mechanism (short flat circuits fade riders).
5. **Pattern battery: 6/7 pass, one honest, diagnosed failure.** Free-riding
   pays; tragedy of the peloton; winners ride sheltered; pull share is tiny;
   organised teams win; weak riders pay more for cooperating (the Hoenigman
   2011 docking pattern). The failure: no finale pace spike — the calibrated
   field red-lines from the gun and fades, because the fitted positional
   urgency is already strong mid-race. Like the drop-rate residual, the
   failure *localises* a misspecification (`docs/validation.md` §2). The
   validation claim is pattern-oriented on a correctly-stated
   **criterium-scale referent**, not a curve fit.

## Improvements over v0.4 — what and why

| # | Improvement | Why |
|---|---|---|
| 0a | **Riders live in a Mesa `ContinuousSpace`** (space refactor) | Positions are now first-class Mesa state (`agent.pos`), synced from track coordinates each step — Mesa tooling and SolaraViz work natively. Dynamics stay in arc-length (racing distance is along-track); tested invariant `pos == track.xy(s, lane)`. |
| 0b | **Interactive browser app** (`peloton/viz/server.py`, SolaraViz) | The Mesa-3 replacement for the course's Mesa-2 `server.py` (that API was removed in 3.0): strategy dropdown from the plugin registry, sliders, live space view + charts. `animate.py` kept as the offline mp4 renderer. Includes a documented workaround for Mesa 3.5.1's `_scatter` zorder bug. |
| 1 | **Equilibria measured, not asserted** (deviation/EGTA harness) | The headline claims of v0.1–v0.4 were design intent, not evidence; measurement *overturned two of them* (interior PG equilibrium; no anti-coordination in hawk_dove) — the strongest possible argument for the tool. |
| 2 | **Winner's-curse fix in calibration** (holdout seeds) | Fitted-on-same-seeds losses are optimistically biased; the quotable number is now the holdout loss. |
| 3 | **Paired statistics + 95 % CIs** (`analysis/stats.py`) | The harness already used common random numbers; v0.5 finally analyses it as the paired design it is, with stated n. |
| 4 | **Sensitivity analysis exists** (Morris/Sobol/dt + batch runner) | Explicitly required by the course rubric; absent in all prior versions. |
| 5 | **Evolution back on current physics** | v0.1's result predates the W′ cap and 2-D position — strictly a different model; course brief asked for learned probabilities. |
| 6 | **Per-rider strategy parameters** (`strategy_params` list) | Unlocks deviation experiments, evolutionary populations, heterogeneous fields; closes a v0.4 known limitation. |
| 7 | **QRE language softened** | We compute quantal-response *decision-making*, not a QRE fixed point; claims now match the math. |
| 8 | **Referent system stated honestly** (criterium, not road stage) | The 4 km / 5 min race cannot be validated against 200 km road-race phenomena; the scale mismatch was v0.1–v0.4's biggest unexamined assumption. |
| 9 | **ODD+ description** | Standard ABM reporting protocol; scaffolded in the team's own Overleaf but never written. |
| 10 | **Multiprocessing batch runner** | SA needs thousands of races; 7× throughput, deterministic, order-preserving. |

## Figures

```
01_compare_all.png/.md (+_paired.md)   games side-by-side, 95% CI + paired contrasts
02_choice_explainer.png                inside the logit black box
03_calibration.png/.json               fit + holdout to data targets
04_rationality_sweep.png               λ: random play -> directed play
05_deviation_equilibrium.png           measured equilibria (the v0.5 centrepiece)
06_evolution.png                       evolution rediscovers the interior equilibrium
07_sensitivity_morris.png/.json        screening: what drives the behaviour
08_sensitivity_sobol.png/.json         variance decomposition on top factors
09_dt_robustness.png                   numerical robustness (timestep)
validation_battery.json                pattern-oriented validation results
race_discrete_choice.mp4               animation (calibrated game)
```

## How to reproduce

```bash
cd proj-peloton-01-v0.5-prototyping-fable
PY=../.venv/bin/python
$PY -m pytest tests/ -q                                # 24 tests
$PY experiments.py                                     # 01-06 + battery
$PY -m peloton.analysis.sensitivity all --workers 7    # 07-09
$PY -m peloton.analysis.calibrate                      # 03 (fit + holdout)
```

## Known limitations / v0.6 candidates

- Deviation grids use one focal rider per race; richer EGTA (multiple
  deviants, profile sampling) would tighten the BR curves.
- Evolution selects on a single race per generation (noisy fitness);
  averaging fitness over k races would sharpen convergence claims.
- The escalation finding in "hawk_dove" invites a redesigned contest rule if
  true anti-coordination is wanted (explicit pairwise contests with shared
  costs), rather than relabeling.
- Road-race referent (longer course, attrition mechanisms) remains future
  work; the drop-rate residual marks exactly what is missing.
