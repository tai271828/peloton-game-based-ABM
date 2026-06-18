"""Interactive browser visualization — Mesa 3 SolaraViz.

The modern equivalent of the course's Mesa-2 ``server.py``
(`ABM-notebooks/notebooks/1/1-mesa/server.py`): parameter controls, a live
space view, and live charts in the browser. Mesa 2's
``ModularServer``/``CanvasGrid`` API was removed in Mesa 3; this uses
``SolaraViz`` with the model's :class:`mesa.space.ContinuousSpace` (added in
the v0.5 space refactor — rider positions are first-class Mesa positions).

Run from the project root::

    ../.venv/bin/solara run peloton/viz/server.py
    # then open http://localhost:8765

Controls: game theory (any auto-discovered strategy), field size, number of
teams. Riders are coloured by team; captains are stars; the rider currently
in the wind (PULL) gets a black edge; dropped riders grey out.

``viz/animate.py`` is intentionally untouched: it remains the offline mp4
renderer; this module is the interactive view.
"""

from __future__ import annotations

import os
import sys

# `solara run peloton/viz/server.py` loads this file by path, not as a
# package module, so the project root must be put on sys.path explicitly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import matplotlib.pyplot as plt
from mesa.visualization import SolaraViz, Slider, make_plot_component, make_space_component
from mesa.visualization.components import AgentPortrayalStyle

from peloton.actions import Action
from peloton.agent import Role
from peloton.model import RaceModel
from peloton.strategies import available

_TEAM_CMAP = plt.get_cmap("tab10")


def agent_portrayal(agent) -> AgentPortrayalStyle:
    if agent.dropped:
        color = (0.75, 0.75, 0.75, 1.0)
    else:
        color = _TEAM_CMAP(agent.team % 10)
    is_captain = agent.role is Role.CAPTAIN
    pulling = (agent.action is Action.PULL) and not agent.finished
    # NOTE: zorder must stay 1 for every agent. Mesa 3.5.1's _scatter has an
    # operator-precedence bug (`z_order == zorder & mask` instead of
    # `(z_order == zorder) & mask`) that silently drops agents with any other
    # zorder. Track artists are drawn below at zorder 0.5 instead.
    return AgentPortrayalStyle(
        color=color,
        marker="*" if is_captain else "o",
        size=160 if is_captain else 45,
        zorder=1,
        edgecolors="black" if (pulling or is_captain) else "none",
        linewidths=1.2 if pulling else 0.6,
    )


def draw_track(ax) -> None:
    """post_process hook: stadium outline + finish line under the riders."""
    model = _current_model[0]
    track = model.track
    for lane, style in ((0.0, dict(color="0.75", lw=1, ls="--")),
                        (model.lane_hi, dict(color="0.45", lw=1.5)),
                        (model.lane_lo, dict(color="0.45", lw=1.5))):
        xs, ys = track.outline(n=400, lane=lane)
        ax.plot(xs, ys, zorder=0.5, **style)
    fx0, fy0 = track.xy(0.0, model.lane_lo)
    fx1, fy1 = track.xy(0.0, model.lane_hi)
    ax.plot([fx0, fx1], [fy0, fy1], color="crimson", lw=2.5, zorder=0.5)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"step {model.steps} | finished {model.n_finished}"
                 f"/{len(model.agents)} | packs {model._n_packs}",
                 fontsize=10)


# SolaraViz rebuilds the model on parameter change; the post_process hook only
# receives the Axes, so the current model is shared through this one-slot box,
# refreshed by agent_portrayal-free wrapper below.
_current_model: list = [None]


def _tracking_portrayal(agent):
    _current_model[0] = agent.model
    return agent_portrayal(agent)


model_params = {
    "strategy": {
        "type": "Select",
        "value": "lead_out",
        "values": available(),
        "label": "game theory (decision plugin)",
    },
    "n_riders": Slider("riders", value=48, min=12, max=80, step=4, dtype=int),
    "n_teams": Slider("teams", value=8, min=2, max=10, step=1, dtype=int),
    "seed": 7,           # fixed; change here for a different draw
}

space = make_space_component(_tracking_portrayal, post_process=draw_track)
speed_plot = make_plot_component("mean_speed")
race_plot = make_plot_component(["n_packs", "n_finished"])

model = RaceModel(n_riders=48, n_teams=8, strategy="lead_out", seed=7)
_current_model[0] = model

page = SolaraViz(
    model,
    components=[space, speed_plot, race_plot],
    model_params=model_params,
    name="Peloton ABM — game-theory plugins on a stadium track",
)
