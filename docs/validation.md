# Validation — referent system, pattern battery, and explicit de-scopes

## 1. The referent system (corrected in v0.5)

The simulated race is **~3.9 km on a 1.30 km closed stadium circuit,
~5 minutes of racing** — the scale of a **criterium or track race**, *not* a
160–250 km road stage. Versions v0.1–v0.4 implicitly validated against road
race narratives; that scale mismatch was the project's biggest unexamined
assumption (a sharp examiner would puncture it). v0.5 states the referent
honestly:

- **In referent:** finale speeds, sprint speeds, drafting/sheltering shares,
  positional fighting, lead-out delivery, short-race energy budgeting.
- **Out of referent (do not calibrate against):** hour-scale breakaway
  dynamics, attrition/drop rates of long stages, feeding/pacing strategy.

The road-race path is mechanical (laps are free; recalibrate) but is **future
work**, not a v0.5 claim. The calibration's drop-rate residual
(`docs/game-theory.md` §4.4) marks exactly the mechanisms that path needs.

## 2. Validation strategy: patterns, not curve fits

With a stylised model and stylized-fact targets, a quantitative telemetry fit
would be weak evidence. The defensible claim is **pattern-oriented
modelling** (Grimm et al.): one parameterisation simultaneously reproduces
multiple *independent* qualitative patterns of real pack racing. Every entry
below is re-computed on v0.5 physics by `experiments.compute_battery()`
(results in `figures/validation_battery.json`; no cross-version citations).

| # | pattern (real-world source) | v0.5 evidence | result |
|---|---|---|---|
| P1 | Doing the front work costs results — pulling correlates with losing (folk wisdom; Hoenigman et al. 2011) | corr(p_coop, finish rank) = **+0.34** (p < 1e-15, 12 races × 50 riders) | ✅ |
| P2 | A field where nobody works is collectively slowest — the tragedy of the peloton (Hoenigman 2011; race lore: "nobody pulls, everyone loses") | winner time **311 s** (q=0) vs **241 s** (q=0.3), Wilcoxon p ≈ 0.008 | ✅ |
| P3 | Sprint winners ride sheltered and are delivered to the finale (lead-out accounts) | calibrated game: winner drafted share **0.68** vs field **0.48** | ✅ |
| P4 | Only a small minority of decisions are front-work (paceline rotation share) | calibrated game: PULL share **0.021** of decisions | ✅ |
| P5 | Organised teams beat disorganised opposition (modern lead-out era) | mixed field: lead-out captain rank **0.053** vs selfish-team **0.241** | ✅ |
| P6 | Pace spikes in the finale (positioning fight + sprint) | last 10 % of race time **46.8 km/h** vs overall **53.5 km/h** — the calibrated field rides flat-out from the gun and *fades* | ❌ **honest failure** |
| P7 | Docking vs Hoenigman et al. (2011): cooperating costs weak riders more than strong | rank-vs-p_coop slope: weak tercile **0.61** > strong tercile **0.16** | ✅ |

Score: **6 / 7** (`figures/validation_battery.json` holds exact values; the
table regenerates via `experiments.compute_battery()`).

**Reading the P6 failure.** Under the fitted weights (position weighted ~4×
energy, λ = 8), riders red-line from the start — the positional-urgency term
is already strong mid-race — so there is no reserve left to lift the pace in
the finale; the tail of the race is exhausted riders fading under the W′
cap. Like the drop-rate residual, this failure *localises* a
misspecification instead of hiding it: a finale spike needs either sharper
urgency curvature (flat early, steep late) or an explicit energy-target
term. A 6/7 battery with a diagnosed failure is stronger evidence of model
understanding than a tuned 7/7.

Complementary *internal* validation:

- **Equilibrium consistency** (fig 05/06): the evolved cooperation level
  (p̂ = 0.19) coincides with the measured best-response fixed point
  (q\* ≈ 0.2) — two independent methods, one answer.
- **Null-model anchoring** (fig 04): λ = 0 reproduces the `random` baseline;
  emergent observables move smoothly and monotonically as rationality rises.
- **Calibration holdout** (fig 03): fit loss 0.570 vs holdout 0.580 — the fit
  is not a seed artifact; the deliberately-kept drop-rate misfit localises
  missing mechanisms rather than being hidden.

## 3. Explicit de-scopes (so the report doesn't silently under-deliver)

1. **Breakaway-and-chase.** Promised by the team's Overleaf abstract;
   implemented in no version. De-scoped: it is a new mechanism with new
   failure modes and cannot be validated on the v0.5 timeline. The report
   should either de-scope it explicitly (recommended) or re-cut the abstract.
2. **QRE equilibrium.** The discrete-choice game is quantal-response
   *decision-making*; no beliefs-consistent fixed point is computed. Claims
   are worded accordingly (`docs/game-theory.md` §4.1).
3. **Road-race referent.** See §1. Drop-rate/attrition phenomena are out of
   scope and marked as the diagnosed residual.
4. **Hawk–Dove as designed ≠ as measured.** The contest rules generate
   strategic complementarity (escalation), not anti-coordination (fig 05c).
   v0.5 reports the measured game rather than the intended one; redesigning
   the contest to recover true Hawk–Dove structure is future work.
