"""Game theory #2 — positioning as a Hawk–Dove (chicken) game.

Here the contested resource is the **sheltered wheel**, not the pace. Whenever
two riders want the same draft slot they play a pairwise Hawk–Dove game:

* **Hawk** — ``SPEED_UP`` to seize/hold the wheel. Aggressive and costly; if the
  rival is also a Hawk, *both* burn energy fighting (the mutual-Hawk payoff).
* **Dove** — ``SLOW_DOWN`` / ``KEEP`` to yield the wheel and save energy.

This is anti-coordination: the population settles on a *mixed* aggression rate
rather than everyone doing the same thing — a structurally different equilibrium
from the public-goods dilemma, yet expressed through the **same action
vocabulary**. See ``docs/game-theory.md`` §2.

Decision rule:

* **Sprint zone**: all-out — ``SPEED_UP`` (everyone is a Hawk at the line).
* **Dropped / very low energy**: ``SLOW_DOWN`` to recover.
* If **already sheltered** and no challenger is pressing from behind: ``DRAFT``
  (hold the good spot cheaply).
* If a **wheel ahead is contested** (a rival is alongside / just behind, eyeing
  the same shelter), play Hawk with probability ``p_hawk`` → ``SPEED_UP``, else
  Dove → ``SLOW_DOWN``.
* Otherwise move up to grab open shelter — ``SPEED_UP`` if a wheel is reachable,
  else ``KEEP``.

``p_hawk`` rises when energy is high and the finish is near (cheap to fight,
worth fighting), capturing the Hawk–Dove intuition that aggression scales with
the value of the prize and the ability to pay for it.
"""

from __future__ import annotations

from peloton.actions import Action
from peloton.agent import Perception, SelfView
from peloton.strategies.base import BaseStrategy, register_strategy


@register_strategy("hawk_dove")
class HawkDoveStrategy(BaseStrategy):
    """Pairwise contest for the sheltered wheel.

    Params
    ------
    base_hawk : float
        Baseline aggression probability.
    energy_weight, finish_weight : float
        How strongly a full battery and a near finish push toward Hawk.
    challenge_gap_m : float
        A rider this close behind (and roughly alongside) counts as a challenger.
    low_energy : float
        Energy fraction below which the rider yields to recover.
    """


    def __init__(self, params: dict | None = None):
        super().__init__(params)
        self.base_hawk = self.params.get("base_hawk", 0.35)
        self.energy_weight = self.params.get("energy_weight", 0.35)
        self.finish_weight = self.params.get("finish_weight", 0.30)
        self.challenge_gap_m = self.params.get("challenge_gap_m", 6.0)
        self.low_energy = self.params.get("low_energy", 0.12)

    # -- the Hawk probability given current value/ability to fight ------
    def _p_hawk(self, view: SelfView) -> float:
        p = (self.base_hawk
             + self.energy_weight * view.energy_frac
             + self.finish_weight * view.progress)
        return max(0.0, min(1.0, p))

    def _challenged(self, perc: Perception) -> bool:
        nb = perc.behind[0] if perc.behind else None
        return nb is not None and -nb.gap <= self.challenge_gap_m

    def decide(self, view: SelfView, perc: Perception) -> Action:
        # Endgame: pure sprint, everyone fights.
        if perc.in_sprint_zone:
            return Action.SPEED_UP

        # Self-preservation.
        if view.energy_frac < self.low_energy:
            return Action.SLOW_DOWN

        sheltered = view.is_drafting

        # Holding good shelter and nobody pressing -> sit in cheaply.
        if sheltered and not self._challenged(perc):
            return Action.DRAFT

        # A contest is on (being challenged, or fighting to take a wheel).
        contested = self._challenged(perc) or (perc.nearest_ahead is not None)
        if contested:
            if self.rng.random() < self._p_hawk(view):
                return Action.SPEED_UP        # Hawk: seize / hold the wheel
            return Action.SLOW_DOWN           # Dove: yield, save energy

        # Open road ahead: ease up to a wheel if there is one, else hold.
        return Action.SPEED_UP if perc.nearest_ahead is not None else Action.KEEP
