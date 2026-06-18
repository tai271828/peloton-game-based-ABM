"""The plug-and-play decision interface — the "black box" contract.

A *game theory* in this project is any object that implements :class:`Strategy`.
It receives two frozen, read-only views (``SelfView`` of the rider's own traits,
``Perception`` of its local surroundings) and returns exactly one
:class:`~peloton.actions.Action`. It must never import the model, mutate state,
or compute speed/energy — those are the model's job. Keeping this contract is
what lets a whole field's game theory be swapped with a single config flag.

Registering a new game (v0.4): decorate the class with
:func:`register_strategy` and drop the file in this package — it is
auto-discovered at import time. No registry file to edit, no other change
anywhere:

    from peloton.strategies.base import BaseStrategy, register_strategy

    @register_strategy("my_game")
    class MyGame(BaseStrategy):
        def decide(self, view, perc):
            ...

See ``docs/specification.md`` and ``docs/game-theory.md`` for the concrete games.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from peloton.actions import Action
from peloton.agent import Perception, SelfView

#: name -> strategy class; filled by the @register_strategy decorator.
STRATEGIES: dict[str, type] = {}


def register_strategy(name: str):
    """Class decorator: make a strategy available under ``name``.

    Sets ``cls.name`` and adds the class to :data:`STRATEGIES`, which
    ``peloton.strategies.make_strategy`` reads. Duplicate names raise
    immediately so two plugin files cannot silently shadow each other.
    """
    def deco(cls):
        if name in STRATEGIES and STRATEGIES[name] is not cls:
            raise ValueError(f"strategy name {name!r} is already registered "
                             f"by {STRATEGIES[name].__qualname__}")
        cls.name = name
        STRATEGIES[name] = cls
        return cls
    return deco


@runtime_checkable
class Strategy(Protocol):
    name: str

    def reset(self, rng) -> None:
        """Per-race initialisation (draw private parameters, clear memory)."""
        ...

    def decide(self, view: SelfView, perc: Perception) -> Action:
        """Return the single action to execute this step."""
        ...


class BaseStrategy:
    """Convenience base: stores params + a per-race RNG, no-op ``reset``."""

    name = "base"

    def __init__(self, params: dict | None = None):
        self.params = params or {}
        self.rng = None

    def reset(self, rng) -> None:
        self.rng = rng

    def decide(self, view: SelfView, perc: Perception) -> Action:  # pragma: no cover
        raise NotImplementedError
