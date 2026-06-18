"""Game theory #3 — the team lead-out train (a coordination game).

This is the v0.3 addition. Unlike the public-goods and Hawk–Dove games, where
every rider plays for itself, the lead-out is a **team** game with **roles**:

* **Domestiques** sacrifice themselves for the team. Their job is to ride at the
  front breaking the wind (``PULL``), sheltering their captain and driving the
  pace — spending *their* battery so the captain doesn't have to.
* The **captain** is the designated finisher. Its job is to **conserve**: sit in
  the draft all race (``DRAFT``), arrive at the sprint with a near-full battery,
  and unleash it (``SPEED_UP``) at the line.

The strategic content (full treatment in ``docs/game-theory.md``):

* **Within a team** it is an *altruistic coordination* problem. A domestique that
  pulls finishes badly *itself*, but the unit it belongs to — the team, scored by
  its captain's result — does far better. Roles solve the coordination: everyone
  agrees who the captain is, so the sacrifice is not wasted.
* **Between teams** the captains (each riding on a private "energy subsidy" from
  its train) compete in the sprint. A team that organises a lead-out delivers a
  fresher captain than a team that does not — so the lead-out is *collectively
  rational* even though it is individually costly for the domestiques.

The strategy reads the generic ``role`` the model assigns (captain = strongest
rider per team) via ``SelfView.is_captain`` and ``Perception.captain_of(team)``.
The model knows nothing about lead-outs; all the team logic lives here.
"""

from __future__ import annotations

from peloton.actions import Action
from peloton.agent import Perception, SelfView
from peloton.strategies.base import BaseStrategy, register_strategy


@register_strategy("lead_out")
class LeadOutStrategy(BaseStrategy):
    """Role-conditioned team strategy: domestiques lead out, captains conserve.

    Params
    ------
    domestique_low_energy : float
        Energy fraction below which a domestique peels off to recover.
    captain_low_energy : float
        Energy fraction below which even the captain eases off (rarely hit).
    catch_up_gap_m : float
        If a domestique's captain is more than this far up the road, the
        domestique bridges across (SPEED_UP) instead of pulling.
    """


    def __init__(self, params: dict | None = None):
        super().__init__(params)
        # default 0.20: swing off just before the W' fatigue cap (knee 0.25)
        # would turn a spent domestique into the slow wheel blocking its team.
        self.dom_low = self.params.get("domestique_low_energy", 0.20)
        self.cap_low = self.params.get("captain_low_energy", 0.05)
        self.catch_m = self.params.get("catch_up_gap_m", 5.0)
        self.stale_wheel = self.params.get("stale_wheel_mps", 0.3)

    # -- captain: conserve all race, then sprint -----------------------
    def _decide_captain(self, view: SelfView, perc: Perception) -> Action:
        if perc.in_sprint_zone:
            return Action.SPEED_UP                 # unleash the saved battery
        if view.energy_frac < self.cap_low:
            return Action.SLOW_DOWN
        # v0.4 fix: don't die with your train. If the wheel I'm on is clearly
        # slower than my local group, my train has blown — jump to faster
        # wheels (any team's) instead of matching a crawling domestique.
        # In v0.3 the captain blindly DRAFTed its nearest wheel, so a dying
        # train towed its captain backwards out of the race.
        nb = perc.nearest_ahead
        if nb is not None and nb.speed < perc.pack_speed - self.stale_wheel:
            return Action.SPEED_UP                 # move up to live wheels
        # sit in the shelter and save everything for the finish.
        return Action.DRAFT if nb is not None else Action.KEEP

    # -- domestique: do the work, then you're spent --------------------
    def _decide_domestique(self, view: SelfView, perc: Perception) -> Action:
        if perc.in_sprint_zone:
            return Action.KEEP                      # job done; the finish is the captain's
        if view.energy_frac < self.dom_low:
            # blown — swing off and get OUT of the line (v0.4: a spent
            # domestique crawling on the front used to become the slow wheel
            # its own captain was glued to).
            return Action.SLOW_DOWN
        # if my captain has slipped up the road, bridge across to it ...
        cap = perc.captain_of(view.team)
        if cap is not None and cap.gap > self.catch_m:
            return Action.SPEED_UP
        # ... otherwise the default job is to ride the front and break the wind.
        return Action.PULL

    def decide(self, view: SelfView, perc: Perception) -> Action:
        if view.is_captain:
            return self._decide_captain(view, perc)
        return self._decide_domestique(view, perc)
