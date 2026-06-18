# ODD+ Model Description — Peloton ABM v0.5

Following the ODD protocol (Grimm et al. 2006, 2020 update), with the "+"
extensions for decision-making models. Self-contained: readable without the
code. Implementation: Python / Mesa 3.5, package `peloton/`.

---

## 1. Purpose and patterns

**Purpose.** To study how game-theoretic decision rules produce the emergent
collective dynamics of competitive pack cycling — drafting cooperation,
positional contests, team lead-outs — on a closed criterium-style circuit,
and to provide a framework in which alternative game theories can be swapped
and compared under identical physics, including one (logit discrete choice)
whose parameters can be calibrated against observed competition data.

**Patterns used for evaluation** (pattern-oriented modelling; see
`docs/validation.md`): winners ride sheltered and are delivered to the
finale; front-work (pulling) shares are low; pulling correlates with worse
finishes; an all-defecting field is collectively slowest; organised teams
beat disorganised ones; pace spikes in the finale.

## 2. Entities, state variables, and scales

**Entities.** (i) *Cyclists* (agents); (ii) the *track* (closed stadium
course) together with a Mesa ``ContinuousSpace`` holding each rider's true
(x, y) position — the spatial system of record, sized to the track's
bounding box; (iii) the *model/race* (scheduler, physics, data collection).
Teams are implicit collectives via a shared team id; one rider per team
carries the `CAPTAIN` role label.

*Space design note:* rider **dynamics** run in track coordinates — arc-length
``s`` plus lateral ``lane`` — because racing distance and "who is ahead" are
along-track notions (a Euclidean neighbourhood would treat riders across the
infield as close). After each step the model syncs every rider's
``track.xy(s, lane)`` into the ``ContinuousSpace``, so Mesa tooling
(SolaraViz space components, Euclidean queries, ``agent.pos``) sees native
positions while perception stays arc-length-based.

**Cyclist state variables.**

| variable | units | meaning |
|---|---|---|
| `skill` | – (~1.0) | power-to-weight multiplier; scales power, battery, sprint |
| `energy`, `energy_max` | a.u. | anaerobic reserve (W′-like battery) |
| `aer_power` | a.u. | sustainable aerobic power (skill-scaled) |
| `aero_speed` | m/s | speed sustainable on aerobic power alone |
| `s`, `lane` | m | arc-length on loop; lateral offset |
| `distance` | m | cumulative distance (ranking variable) |
| `speed` | m/s | current speed |
| `team`, `role` | – | team id; CAPTAIN/DOMESTIQUE label |
| `action` | – | this step's chosen action (5-symbol vocabulary) |
| `is_drafting`, `dropped`, `finished`, `finish_rank` | – | status |
| strategy object | – | plugged-in decision rule + its parameters |

**Track.** Stadium (discorectangle): two straights (`straight_m` = 400 m)
joined by semicircular bends (`bend_radius_m` = 80 m); loop ≈ 1303 m;
`n_lanes` = 6 lateral lines, 1 m apart.

**Scales.** Time step `dt` = 1 s (robustness: `figures/09_dt_robustness.png`);
race = 3 laps ≈ 3.9 km ≈ 4–6 min — i.e. a **criterium/track-race** scale, not
a road stage (referent statement in `docs/validation.md`). Default field:
48 riders, 8 teams.

## 3. Process overview and scheduling

Simultaneous activation each step (decisions collected, then resolved — no
order bias):

1. **Perceive** — each active rider gets read-only views: `SelfView` (own
   traits) and `Perception` (neighbours within `sense_radius_m` = 20 m ahead
   and behind, local pack speed, distance to finish, sprint-zone flag).
2. **Decide** — the plugged-in strategy maps views → one action:
   `PULL | DRAFT | SPEED_UP | KEEP | SLOW_DOWN`.
3. **Resolve** — actions → target speed + lane intent; drafting shelter
   resolved geometrically (wheel within `draft_gap_m` = 8 m ahead, lateral
   offset ≤ `draft_lane_m` = 1.5 m; `PULL` forces full wind).
4. **Dynamics** — speed relaxes toward target (`accel_tau` = 2 s), clamped to
   [`v_min`, `v_max`] and to the **W′ fatigue cap** (submodel 7.2); energy
   updated (submodel 7.2); battery empty ⇒ `dropped`.
5. **Move** — advance `s`/`distance`; lap and finish bookkeeping; finishing
   order assigns `finish_rank` (the payoff). Lateral separation pass keeps
   riders from overlapping.
6. **Observe** — online per-agent counters always; optional full
   DataCollector snapshots (`collect=True`).

## 4. Design concepts

- **Basic principles.** Public-goods dilemmas (drafting), anti-coordination
  (Hawk–Dove position contests), team coordination with roles (lead-out),
  and discrete-choice/quantal-response decision-making with bounded
  rationality λ.
- **Emergence.** Pack formation and splitting, paceline rotation, the
  energy funnel into captains, interior cooperation levels, finale pace
  spikes — none scripted; all arise from action choices through one physics.
- **Adaptation.** Within a race, strategies condition on state (energy,
  progress, neighbours). Across races, `analysis/evolution.py` evolves
  `p_coop` by selection on finish rank.
- **Objectives.** Finishing position (rank 0 = winner). The discrete-choice
  game encodes this via the shadow price of energy (worthless at the line)
  and rising positional urgency.
- **Learning.** Race-to-race evolutionary selection (mutation sd 0.05) on
  cooperation tendency; no within-race learning.
- **Prediction.** None explicit; the shadow-price term is an implicit
  prediction that saved energy has future value proportional to remaining
  distance.
- **Sensing.** Strictly local: neighbours within 20 m, own physiology,
  distance to finish. No global knowledge, no radio.
- **Interaction.** Indirect through aerodynamics (shelter) and the shared
  finishing order; direct through positional contention (lane separation).
- **Stochasticity.** Skill draws N(1, 0.12) clipped to [0.75, 1.30]; action
  sampling in probabilistic strategies (logit, p_coop, p_hawk); start-grid
  assignment. Single seeded RNG (Mesa `rng`); common random numbers across
  compared configurations.
- **Collectives.** Teams (shared id; captain role assigned to the
  highest-skill member). Packs emerge from proximity; they are observed
  (counted by gap threshold `pack_gap_m` = 12 m), not imposed.
- **Observation.** Standard metric set per race (`analysis/metrics.py`):
  speeds, finish times/spread, sheltered shares, per-action decision shares,
  winner profile; plus optional full trajectories for animation.

## 5. Initialization

48 riders in a staggered start grid (`start_gap_m` = 2.5 m spacing, 6-lane
block), full batteries, speed `v_cruise` = 12 m/s, teams round-robin, one
captain per team (highest skill). Strategy assignment: a single game for the
whole field, an explicit per-rider list, or a stochastic mix. All defaults in
`peloton/params.py` (single source of truth).

## 6. Input data

No time-series forcing. The *calibration* path consumes
`data/stylized_facts.csv` (target observables with weights and provenance;
shipped values are documented stylized facts intended to be replaced by the
user's own measurements — `data/README.md`).

## 7. Submodels

**7.1 Drafting.** A rider is sheltered iff a wheel is within `draft_gap_m`
ahead and within `draft_lane_m` laterally; sheltered aero cost is multiplied
by `draft_factor` = 0.62. `PULL` is always unsheltered by definition.

**7.2 Energy (W′ battery) and fatigue cap.** Aero power
`P = aero_coeff·(v/v_ref)³` (×`draft_factor` if sheltered). Above
`aer_power`: battery drains at `drain_rate·(P − aer_power)·dt`; below:
recovers at `recover_rate·(aer_power − P)·dt`, capped at `energy_max`.
**Fatigue cap:** below battery fraction `fatigue_knee` = 0.25, the maximum
sustainable speed falls linearly from `v_max` to the rider's `aero_speed`
(`v_ref·(aer_power/aero_coeff)^{1/3}`) at empty — the W′-balance constraint
(you cannot ride supra-threshold on an empty anaerobic tank).

**7.3 Sprint.** Inside the last `sprint_m` = 250 m, speed is
`v_sprint_min + (top − v_sprint_min)·(energy/energy_max)` with
`top = v_sprint_min + (v_sprint_max − v_sprint_min)·skill`, draining
`sprint_drain` per second: leftover battery converts to finishing speed.

**7.4 Decision submodels (plugins; full math in `docs/game-theory.md`).**
- `public_goods`: PULL with probability `p_coop`, else DRAFT (low-energy
  guard; sprint = all-out).
- `hawk_dove`: contest for the wheel; Hawk (`SPEED_UP`) with probability
  rising in energy and race progress, Dove yields.
- `lead_out`: role-conditioned — domestiques PULL (swing off below 0.20
  battery), captains DRAFT and never follow a wheel slower than the local
  group; sprint all-out.
- `discrete_choice`: logit choice `P(a) ∝ exp(λ·u(a))` over
  `u(a) = −w_cost·cost(a)·shadow·scarcity + w_shelter·shelter(a)
  + w_position·advance(a)·urgency`; parameters calibrated to data
  (`analysis/calibrate.py`, holdout-evaluated).
- `random`: uniform action choice (null model; the λ = 0 limit).

**7.5 Lateral dynamics.** Lane moves bounded by `lane_step_m` per step
toward the action's lateral intent; a separation pass enforces minimum
spacing (`sep_s_m`, `sep_lane_m`). Lanes are positioning/legibility, not an
energy term.

---

### Parameter table (defaults; ranges explored in SA)

See `peloton/params.py` for the complete list with comments; the ten
behavioural/physical factors and their SA ranges are in
`peloton/analysis/sensitivity.py::FACTORS`; SA results in
`figures/07–08_sensitivity_*.png`, numerical robustness in
`figures/09_dt_robustness.png`.
