"""Game theory #4 — binary discrete choice / logit (v0.6, the data-facing game).

v0.6 reframes the rider's move as the **binary cooperation dilemma** at the
heart of a peloton: each step a rider either

* **PULL = cooperate** — take the wind, drive the pace, shelter the riders
  behind (a public good paid for in energy), or
* **DRAFT = defect** — tuck into the slipstream, save the battery for itself.

The choice is made with a **binary logit** over an interpretable utility
difference (McKelvey & Palfrey quantal response; the framework of the course's
``3-discrete-choice`` notebook):

    P(PULL) = logistic( lam * ( U(PULL) - U(DRAFT) ) )

Everything is built from the v0.6 per-rider traits — **max velocity** and
**stamina** — plus the race **state** (battery, progress, distance to finish):

    U(PULL)  = - w_cost * extra_cost * shadow * scarcity   # energy you burn by
                                                           # taking the wind...
               + w_team * team_help                        # ...repaid as shelter
                                                           # for your teammates
    U(DRAFT) =   w_pos  * sprint_win * urgency             # hoard for a sprint
                                                           # you can actually win

where

* ``shadow``   = remaining race fraction — energy is precious early, worthless
  at the line (so riders naturally empty the tank in the finale);
* ``scarcity`` = 1 + (1 - battery) — a near-empty battery makes spending dearer;
* ``urgency``  = 0.25 + 1.75 * progress² — positional value rises to the finish;
* ``extra_cost`` = the energy premium of pulling over drafting (= ``draft_save``
  of the aero cost), priced by the cubic aero term;
* ``sprint_win`` = logistic in (v_max, battery) — the rider's odds of winning a
  sprint *right now*. This term is why the **2×2 cooperation table** of the
  proposal **emerges instead of being hard-coded**: a strong, fresh rider has
  high ``sprint_win`` → high DRAFT utility → defects to save for the sprint; a
  weak or empty rider has low ``sprint_win`` → nothing to save for → cooperates.

Parameters (all fittable; defaults below)
-----------------------------------------
w_cost      weight on the energy cost of pulling          (>= 0)
w_team      weight on sheltering teammates (cooperation)  (>= 0)
w_pos       weight on saving for a winnable sprint        (>= 0)
lam         rationality / logit sharpness                 (>= 0)
draft_save  fractional energy saving from drafting        (0..1)
v_ref       speed (m/s) normalising the aero cost
k_v, k_b    sprint-win sensitivity to v_max and battery
vmax_ref    centre (m/s) for the v_max term in sprint_win
vmax_spread scale  (m/s) for the v_max term in sprint_win
"""

from __future__ import annotations

import math

from peloton.actions import Action
from peloton.agent import Perception, SelfView
from peloton.strategies.base import BaseStrategy, register_strategy


def _logistic(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


@register_strategy("discrete_choice")
class DiscreteChoiceStrategy(BaseStrategy):
    """Binary logit over cooperate(PULL) / defect(DRAFT)."""

    def __init__(self, params: dict | None = None):
        super().__init__(params)
        g = self.params.get
        self.w_cost = g("w_cost", 1.0)
        self.w_team = g("w_team", 0.5)
        self.w_pos = g("w_pos", 1.0)
        self.lam = g("lam", 4.0)
        self.draft_save = g("draft_save", 0.38)
        self.v_ref = g("v_ref", 13.9)
        self.k_v = g("k_v", 3.0)
        self.k_b = g("k_b", 2.0)
        self.vmax_ref = g("vmax_ref", 17.5)
        self.vmax_spread = g("vmax_spread", 3.0)

    # -- the probability of cooperating (pulling) this step --------------
    def prob_pull(self, view: SelfView, perc: Perception) -> float:
        battery = view.energy_frac
        progress = view.progress

        shadow = max(0.0, 1.0 - progress)
        scarcity = 1.0 + (1.0 - battery)
        urgency = 0.25 + 1.75 * progress ** 2

        # energy premium of taking the wind vs sitting in the draft.
        speed = max(view.speed, 1e-6)
        aero_cost = (speed / self.v_ref) ** 3
        extra_cost = self.draft_save * aero_cost

        # odds of winning a sprint *now*: strong + fresh => high.
        sprint_win = _logistic(
            self.k_v * (view.v_max - self.vmax_ref) / self.vmax_spread
            + self.k_b * (battery - 0.5))

        # cooperation payoff: a domestique with a captain to shelter gains by
        # pulling; a captain (or a lone rider) has little teammate to work for.
        captain = perc.captain_of(view.team)
        if not view.is_captain and captain is not None:
            team_help = 1.0
        else:
            team_help = 0.2

        # force the agent make a decision to pull or draft
        u_pull = -self.w_cost * extra_cost * shadow * scarcity \
            + self.w_team * team_help
        u_draft = self.w_pos * sprint_win * urgency
        return _logistic(self.lam * (u_pull - u_draft))

    def decide(self, view: SelfView, perc: Perception) -> Action:
        # at the very front there is no wheel to draft — you must pull.
        if perc.nearest_ahead is None:
            return Action.PULL
        return Action.PULL if self.rng.random() < self.prob_pull(view, perc) \
            else Action.DRAFT
