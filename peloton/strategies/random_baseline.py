"""Null model — uniform random action each step.

Not a game theory: a *baseline*. Comparing any real strategy against this one
separates "emergent behaviour produced by the decision rule" from "behaviour
the physics produces no matter what" (packs still form, the sprint still
decides, etc.). It is also exactly the zero-rationality (λ = 0) limit of the
``discrete_choice`` quantal-response strategy, which makes the rationality
sweep in the experiments interpretable end to end.

This file is itself the demonstration of the v0.4 plugin contract: it was
added by dropping one file in this directory — no registry edit, no core edit.
"""

from __future__ import annotations

from peloton.actions import Action
from peloton.agent import Perception, SelfView
from peloton.strategies.base import BaseStrategy, register_strategy

_ACTIONS = tuple(Action)


@register_strategy("random")
class RandomBaseline(BaseStrategy):
    def decide(self, view: SelfView, perc: Perception) -> Action:
        return self.rng.choice(_ACTIONS)
