"""The :class:`Cyclist` agent and the read-only views handed to strategies.

A cyclist owns the **common traits** every game shares (skill, energy/stamina,
team) and the race state, but it delegates *what to do next* to a plugged-in
:class:`~strategies.base.Strategy`. Each step the agent builds two frozen views —
:class:`SelfView` (its own traits) and :class:`Perception` (strictly local
observations) — calls ``strategy.decide(view, perc)``, and stores the returned
:class:`~core.actions.Action` for the model to resolve. The agent never computes
speed or energy itself; the model does, so physics is identical across games.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from mesa import Agent

from peloton.actions import Action


class Role(enum.Enum):
    """A rider's role within its team.

    The framework only *assigns and reports* roles; what (if anything) a role
    means strategically is entirely up to the plugged-in game. A team game may
    read them via ``SelfView.is_captain`` / ``Perception.captain_of``; a game that
    does not care about teams simply ignores them.
    """

    CAPTAIN = "captain"        # the team's designated finisher (sprinter)
    DOMESTIQUE = "domestique"  # a teammate whose job is to shelter the captain

    def __repr__(self) -> str:
        return self.value


# --------------------------------------------------------------------------
# Read-only views: the ONLY information a strategy may see.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Neighbor:
    """A nearby rider, as seen by the perceiving agent."""
    gap: float        # signed arc-length gap (m); >0 = ahead, <0 = behind
    lane: float       # lateral offset of the neighbour
    speed: float      # m/s
    team: int
    is_captain: bool  # is this neighbour its team's captain?


@dataclass(frozen=True)
class SelfView:
    """The agent's own traits — its "dashboard"."""
    skill: float          # v0.6: alias of `stamina`, kept for back-compat
    energy: float         # current battery (v0.6: normalised B in [0,1])
    energy_max: float     # v0.6: 1.0 (battery is already a fraction)
    speed: float          # m/s
    team: int
    is_drafting: bool     # was I sheltered last step?
    progress: float       # fraction of the race completed (0..1)
    is_captain: bool      # am I my team's captain?
    v_max: float          # v0.6 trait: this rider's max velocity (m/s)
    stamina: float        # v0.6 trait: endurance multiplier (~1.0)

    @property
    def energy_frac(self) -> float:
        return self.energy / self.energy_max if self.energy_max else 0.0


@dataclass(frozen=True)
class Perception:
    """Strictly local observations available to the decision plugin."""
    ahead: tuple[Neighbor, ...]    # neighbours ahead, nearest first
    behind: tuple[Neighbor, ...]   # neighbours behind, nearest first
    pack_speed: float              # mean speed of my local group (m/s)
    dist_to_finish: float          # metres of racing left to the finish line
    in_sprint_zone: bool           # within the last `sprint_m`

    @property
    def nearest_ahead(self) -> Neighbor | None:
        return self.ahead[0] if self.ahead else None

    def teammates(self, team: int) -> tuple[Neighbor, ...]:
        """All perceived neighbours (ahead + behind) on the given team."""
        return tuple(nb for nb in (self.ahead + self.behind) if nb.team == team)

    def captain_of(self, team: int) -> Neighbor | None:
        """Nearest perceived captain of the given team, if any (by |gap|)."""
        mates = [nb for nb in self.teammates(team) if nb.is_captain]
        return min(mates, key=lambda nb: abs(nb.gap)) if mates else None


# --------------------------------------------------------------------------
class Cyclist(Agent):
    """A single rider driven by a plug-and-play decision strategy."""

    def __init__(self, model, v_max: float, stamina: float, team: int, strategy):
        super().__init__(model)
        p = model.params

        # --- v0.6 per-rider traits (replace the single `skill` scalar) ---
        self.v_max = v_max                           # this rider's speed ceiling
        self.stamina = stamina                       # endurance multiplier
        self.skill = stamina                         # back-compat alias (reports)
        # normalised battery in [0, 1]; drains by velocity / stamina (see model).
        self.energy_max = 1.0
        self.energy = 1.0                            # start fully charged
        self.aer_power = p["aer_power"] * stamina    # sustainable aerobic power
        # the speed the aerobic engine alone can hold (floor a dropped rider
        # decays toward): solve aero_coeff * (v / v_ref)^3 = aer_power for v.
        self.aero_speed = p["v_ref"] * (self.aer_power / p["aero_coeff"]) ** (1 / 3)
        self.team = team
        self.role = Role.DOMESTIQUE                  # set per-team by the model
        self.strategy = strategy

        # --- online counters (cheap per-step stats; analysis w/o dataframes) ---
        self.n_steps = 0
        self.n_sheltered = 0
        self.action_counts = {a: 0 for a in Action}
        self.peak_speed = 0.0

        # --- race state ---
        self.s = 0.0                 # arc-length on the loop (m)
        self.lane = 0.0              # lateral offset (m)
        self.speed = p["v_cruise"]
        self.distance = 0.0          # cumulative distance ridden (m)
        self.laps = 0

        self.action = Action.KEEP    # this step's chosen action
        self.is_drafting = False
        self.dropped = False         # ran the battery dry -> off the back
        self.finished = False
        self.finish_rank: int | None = None
        self.finish_time: float | None = None

    def decide(self, view: SelfView, perc: Perception) -> None:
        """Ask the black box for this step's action."""
        self.action = self.strategy.decide(view, perc)

    def __repr__(self) -> str:
        return (f"Cyclist(id={self.unique_id}, team={self.team}, "
                f"skill={self.skill:.2f}, strat={self.strategy.name})")
