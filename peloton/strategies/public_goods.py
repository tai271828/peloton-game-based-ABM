"""Game theory #1 — drafting as an N-player public-goods game.

Pulling at the front breaks the wind for the whole pack: a costly *contribution*
that produces a shared *public good* (pack speed). Drafting is *free-riding* —
cheap, but it adds nothing to the pace. The one-shot rational move is to never
pull (free-ride), yet a pack where nobody pulls crawls: the tragedy of the
peloton. See ``docs/game-theory.md`` §1.

Decision rule (deliberately simple):

* In the **sprint zone**: empty the tank — ``SPEED_UP``.
* If **dropped / very low energy**: ease off to recover — ``SLOW_DOWN``.
* Else play the public-goods move: with probability ``p_coop`` **contribute**
  (``PULL``); otherwise **free-ride** (``DRAFT``) when a wheel is available, or
  ``KEEP`` if there is no one to draft.

``p_coop`` is a fixed per-rider tendency drawn once per race — exactly
Francesca's "probability of cooperation" from the brief. Sweeping it across the
field reproduces the social dilemma (experiments 01–02).
"""

from __future__ import annotations

from peloton.actions import Action
from peloton.agent import Perception, SelfView
from peloton.strategies.base import BaseStrategy, register_strategy


@register_strategy("public_goods")
class PublicGoodsStrategy(BaseStrategy):
    """Probabilistic pull-or-draft contributor.

    Params
    ------
    p_coop : float | None
        Cooperation probability. If ``None`` (default) it is drawn uniformly in
        ``[0, 1]`` per race in :meth:`reset`, giving a heterogeneous field.
    low_energy : float
        Energy fraction below which the rider eases off to recover.
    """


    def __init__(self, params: dict | None = None):
        super().__init__(params)
        self.p_coop = self.params.get("p_coop", None)
        self.low_energy = self.params.get("low_energy", 0.12)

    def reset(self, rng) -> None:
        super().reset(rng)
        if self.params.get("p_coop", None) is None:
            self.p_coop = rng.random()
        else:
            self.p_coop = self.params["p_coop"]

    def decide(self, view: SelfView, perc: Perception) -> Action:
        # Endgame: the game is off, spend everything.
        if perc.in_sprint_zone:
            return Action.SPEED_UP

        # Self-preservation: recover when the battery is nearly flat.
        if view.energy_frac < self.low_energy:
            return Action.SLOW_DOWN

        # The public-goods move.
        if self.rng.random() < self.p_coop:
            return Action.PULL                      # contribute to the public good
        # Free-ride if there is a wheel to sit on, else just hold pace.
        return Action.DRAFT if perc.nearest_ahead is not None else Action.KEEP
