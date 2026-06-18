"""The action vocabulary — the framework's stable "common function returns".

Every cyclist executes exactly **one** :class:`Action` per simulation step. This
is the only thing a decision plugin (a "game theory") is allowed to return, and
its meaning is resolved by the model (``core/model.py``) identically regardless
of which strategy chose it. That uniformity is what makes strategies
hot-swappable — see ``docs/specification.md`` §4–5.
"""

from __future__ import annotations

import enum


class Action(enum.Enum):
    """One discrete move a rider can execute in a step.

    The model maps each action to (target-speed change, wind exposure, lateral
    intent); strategies never touch speed or energy directly.
    """

    PULL = "pull"            # take the front line: full wind, drives the pace
    DRAFT = "draft"          # tuck into shelter behind the rider ahead
    SPEED_UP = "speed_up"    # accelerate by +dv (keep current line)
    KEEP = "keep"            # hold current speed
    SLOW_DOWN = "slow_down"  # decelerate by -dv and recover energy

    def __repr__(self) -> str:  # nicer dataframes / logs
        return self.value
