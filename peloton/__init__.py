"""Core simulation framework for the peloton ABM (v0.3).

This package is *strategy-agnostic*: it defines the action vocabulary, team roles,
the stadium track, the cyclist agent, and the race model. Game-theoretic decision
logic lives entirely in the sibling ``strategies`` package and is plugged in
through the :class:`~strategies.base.Strategy` interface. v0.3 adds generic team
*roles* (captain / domestique) that the model assigns and reports; whether a role
means anything strategically is up to the plugged-in game.
"""

from peloton.actions import Action
from peloton.track import StadiumTrack
from peloton.agent import Cyclist, SelfView, Perception, Neighbor, Role
from peloton.model import RaceModel
from peloton.params import DEFAULT_PARAMS

__all__ = [
    "Action",
    "StadiumTrack",
    "Cyclist",
    "SelfView",
    "Perception",
    "Neighbor",
    "Role",
    "RaceModel",
    "DEFAULT_PARAMS",
]
