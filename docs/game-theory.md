# The Game Theory Under the Hood (v0.4)

Educational companion. §1–§3 recap the stylised games (details in the v0.2/v0.3
docs); §4 is the v0.4 centrepiece — the **discrete-choice / quantal-response
game** and what fitting it to data says about real racing.

> **One-paragraph summary.** v0.2 and v0.3 hand-wrote three game structures
> (public-goods drafting, Hawk–Dove positioning, lead-out team coordination)
> as if we already knew how riders think. v0.4 adds the opposite move, the one
> econometrics makes: write down *what riders care about* (energy, shelter,
> position) as a utility with unknown weights, let each rider choose actions
> by **logit / quantal response**, and then **fit the weights to observed
> racing data**. The fitted weights read back as an interpretation of the
> sport: how heavily energy is priced against position, how much the draft is
> worth, and how close to best-response the field plays.

---

## 0. Common machinery (unchanged contract)

Five actions per step (`PULL`, `DRAFT`, `SPEED_UP`, `KEEP`, `SLOW_DOWN`); one
shared physics: drafting cuts aero cost to ~60 %, supra-threshold riding
drains a W′-like battery, leftover battery converts to sprint speed at the
line. v0.4 adds one physical constraint: **the W′ speed cap** — below a 25 %
battery your max sustainable speed decays toward your aerobic speed. (You
cannot surge on fumes; in v0.3 you could, and it distorted inter-team
results — see §3.)

## 1. `public_goods` — pulling as an N-player social dilemma (v0.2; **measured in v0.5**)

Pull = costly contribution to pack speed; draft = free-ride. The dilemma is
real and reproduced on current physics: corr(p_coop, finish rank) ≈ +0.34
(pulling correlates with losing) and the all-defect field is the slowest
(~311 s at q = 0 vs ~242 s at q ≈ 0.3 — the tragedy of the peloton).

> **v0.5 correction — the equilibrium is interior, not the corner.** Since
> v0.1 we *asserted* "Nash = everyone drafts." The unilateral-deviation
> measurement (`figures/05_deviation_equilibrium.png`) shows otherwise in the
> spatial model: deviation payoffs are **U-shaped** — a focal rider who never
> pulls saves energy but drifts to the *back of the pack* and loses the
> sprint from there, so a little pulling (~0.2–0.3) beats pure free-riding at
> every field level. The measured best response crosses the diagonal at
> **q\* ≈ 0.2: an interior empirical Nash equilibrium**. The corner result
> was an artifact of v0.1's 1-D physics, where packs had no internal
> position. The dilemma survives (equilibrium cooperation is far below the
> social optimum) but its structure is richer than the textbook story —
> consistent with the calibration's "position-dominated racing" and with the
> evolved interior cooperation level (fig 06).

## 2. `hawk_dove` — the contest for the wheel (v0.2; **measured in v0.5**)

Designed as anti-coordination over draft slots; behavioural fingerprint = a
much higher `SPEED_UP` share (comparison dashboard, action-mix panel).

> **v0.5 correction — the measured game is not Hawk–Dove.** Textbook
> anti-coordination predicts a best response that *falls* as field aggression
> rises. The measured best response (`figures/05_deviation_equilibrium.png`,
> panel c) *rises* with field aggression — strategic **complementarity**
> (when everyone fights for wheels, yielding means losing position), with an
> escalation equilibrium at high aggression (≈ 0.8). The hand-written rules
> were Hawk–Dove-*inspired*, but the spatial payoffs they generate are a
> different game. We keep the strategy (and its name, for continuity) and
> report what it actually is — a demonstration of why equilibria must be
> measured, not assumed from the rule's design intent.

## 3. `lead_out` — altruistic team coordination (v0.3, **fixed in v0.4**)

Roles split the team's objective: domestiques pull, the captain shelters and
sprints. v0.3 had an honest known limitation: organised teams *lost* to
disorganised ones in mixed fields, because (a) a rider could surge
indefinitely on an empty battery (physics gap), and (b) the captain blindly
drafted its own blown domestique while the bunch rode away (strategy bug).
v0.4 fixes both — W′ cap + a "don't die with your train" rule (if your wheel
is slower than the local group, move up) — and the real-world expectation now
emerges: **mixed-field captain rank 0.06 (organised) vs 0.25 (selfish);
a lead-out team rider wins 23/24 mixed races.**

The diagnosis-to-fix chain is itself the lesson: the v0.3 misfit located a
missing physical constraint and a wrong behavioural rule, exactly the way
calibration residuals are supposed to be used (§4.4).

---

## 4. `discrete_choice` — quantal response, the data-facing game (v0.4)

### 4.1 The model

Each step, rider *i* scores every action *a*:

```
u(a) = − w_cost · cost(a) · shadow · scarcity     energy expenditure
       + w_shelter · shelter(a)                   value of the draft
       + w_position · advance(a) · urgency        value of moving up
```

- `cost(a)`: relative power of the action (PULL 1.6 … SLOW_DOWN 0.4).
- `shadow = 1 − progress`: the **shadow price of energy** — battery is
  precious with a long race ahead and *worthless at the line*. This single
  term makes riders empty the tank in the finale **without any hard-coded
  sprint mode** (see `figures/02_choice_explainer.png`, panel a).
- `scarcity = 2 − energy_frac`: spending from an empty tank hurts more.
- `urgency = 0.25 + 1.75·progress²`: positioning matters most in the finale —
  the real-world "fight for position with 2–3 km to go" from the project's
  Overleaf notes.

Choice is logit / softmax:  **P(a) ∝ exp(λ·u(a))** — quantal-response
*decision-making* in the sense of McKelvey & Palfrey (1995). λ interpolates
between uniform random play (λ = 0, which is exactly our `random` baseline —
verified: same emergent speeds) and strict best response (λ → ∞).
`figures/04_rationality_sweep.png` shows the emergent observables morphing
smoothly along that bridge. This is the same discrete-choice framework as the
course's `3-discrete-choice` notebook, embedded in an ABM.

> **Scope of the claim (v0.5 correction).** What riders do here is
> quantal-response *decision-making* against the observed race state. A full
> **QRE** is additionally an equilibrium — beliefs consistent with everyone's
> mixed play at a fixed point — which we do **not** compute. We therefore
> describe the game as *logit discrete choice with bounded rationality λ*
> and avoid "QRE equilibrium" claims. (The empirical-equilibrium evidence in
> this project comes from the deviation experiments of
> `figures/05_deviation_equilibrium.png` instead.)

### 4.2 What the *default* weights already produce

With nothing fitted, the utility structure alone reproduces the v0.2 Nash
logic *endogenously*: riders pull in only ~2 % of decisions and draft in ~59 %
— free-riding emerges from prices, not from a hand-written rule.

### 4.3 Fitting to data (the calibration)

`python -m peloton.analysis.calibrate` fits (w_cost, w_shelter, w_position, λ)
to `data/stylized_facts.csv` by weighted relative squared error (coarse grid +
local refinement, seed-averaged). Result on the shipped stylized facts:

```
w_cost = 0.35   w_shelter = 0.28   w_position = 1.40   λ = 8.0
```

Interpretation (auto-generated by `calibrate.interpret`):

- **Position-dominated racing**: energy expenditure is weighted only ~0.25×
  as heavily as positional gain. To look like real sprint finishes, simulated
  riders must care about where they are far more than what it costs.
- **Shelter is a secondary motive** next to positioning — riders draft
  because it is cheap, not because shelter is intrinsically prized.
- **λ = 8**: noisy-but-directed choices — quantal response territory, well
  short of strict best response.

**Identification caveat (read before quoting the numbers).** Logit utilities
are identified only up to scale: multiplying all weights by *c* and dividing
λ by *c* changes nothing. Trust the **ratios** (e.g. w_cost/w_position =
0.25, which was stable across independent fit runs), not absolute values.

The biggest *behavioural* effect of fitting: the simulated **winner's
sheltered share jumps from ~0.13 (default) to ~0.70** against a target of
0.85 — fitting to data *discovers* that winners must ride the draft and be
delivered to the line, the lead-out insight, without ever being told about
teams.

### 4.4 Reading the residual (what the model still can't match)

The remaining loss (~0.57) is almost entirely the `drop_rate` target (4 % of
the field distanced; the simulation produces ~0 %). That is not noise — it is
a **diagnosis**: with the W′ cap, tired simulated riders *fade* but the flat,
short race never breaks them off completely. Matching real drop rates needs a
mechanism this model deliberately lacks (longer races, climbs, crosswind
echelons). Calibration residuals localising model misspecification is
precisely how this pipeline is meant to be used on real data.

### 4.5 Caveat on the shipped targets

`data/stylized_facts.csv` contains literature-level stylized facts
(documented in `data/README.md`), **not** a curated telemetry dataset. The
deliverable is the *pipeline*; swap in your own measurements (any
`race_metrics` observable, including action shares if you have behavioural
data) and refit.

---

## 5. The four games side by side

| | `public_goods` | `hawk_dove` | `lead_out` | `discrete_choice` |
|---|---|---|---|---|
| Family | N-player PD | anti-coordination | team coordination | **quantal response** |
| Rules | hand-written | hand-written | hand-written | **utility + fitted weights** |
| Question it answers | does cooperation collapse? | who fights for the wheel? | do roles beat selfishness? | **what do real riders optimise?** |
| Equilibrium notion | measured by deviation (fig 05) | measured by deviation (fig 05) | role-conditioned | none claimed (bounded-rationality λ) |

All four (plus the `random` null) run on the same physics and compare in one
command: `python -m peloton.analysis.compare`.
