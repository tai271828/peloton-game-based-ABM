"""Strategy plugins — auto-discovered, zero-registration-file design.

v0.2/v0.3 required editing a registry dict to add a game. v0.4 removes even
that: every module in this package is imported at load time, and any class
decorated with ``@register_strategy("name")`` becomes available to
:func:`make_strategy` and to every CLI (`compare`, `animate`, ...).

**Adding a game theory is now exactly one file**, dropped into this directory:

    # peloton/strategies/my_game.py
    from peloton.strategies.base import BaseStrategy, register_strategy
    from peloton.actions import Action

    @register_strategy("my_game")
    class MyGame(BaseStrategy):
        def decide(self, view, perc):
            return Action.KEEP
"""

from __future__ import annotations

import importlib
import pkgutil

from peloton.strategies.base import (BaseStrategy, STRATEGIES, Strategy,
                                     register_strategy)


def _discover() -> None:
    """Import every sibling module so its @register_strategy runs."""
    for mod in pkgutil.iter_modules(__path__):
        if mod.name != "base" and not mod.name.startswith("_"):
            importlib.import_module(f"{__name__}.{mod.name}")


_discover()


def available() -> list[str]:
    """Names of all discovered strategies."""
    return sorted(STRATEGIES)


def make_strategy(name: str, params: dict | None = None) -> Strategy:
    """Instantiate a registered strategy by name."""
    # The classic trick to make plugins
    try:
        cls = STRATEGIES[name]
    except KeyError:
        raise KeyError(
            f"unknown strategy {name!r}; available: {available()}"
        ) from None
    return cls(params or {})


__all__ = ["STRATEGIES", "Strategy", "BaseStrategy", "register_strategy",
           "make_strategy", "available"]
