"""The standard emergent-behaviour metric set, computed from one finished race.

Every strategy is summarised by the *same* observables, so cross-game
comparison (``compare.py``) and data calibration (``calibrate.py``) speak one
language. All metrics derive from the cheap per-agent counters the model keeps
online — no DataCollector required — so they work in ``collect=False`` fast
mode (a v0.4 improvement: v0.2/v0.3 recomputed everything from pandas
dataframes, per experiment file, slowly).

Naming: ``*_kmh`` are km/h, ``*_s`` seconds, ``*_share``/``*_rate`` are 0..1.
"""

from __future__ import annotations

from peloton.actions import Action


def race_metrics(model) -> dict:
    """Summarise a finished (or stopped) race as a flat dict of floats."""
    agents = list(model.agents)
    n = len(agents)
    finished = [a for a in agents if a.finished]
    winner = min(finished, key=lambda a: a.finish_rank) if finished else None

    # field-level speed: distance ridden over time on the bike, averaged.
    speeds = [a.distance / (a.n_steps * model.dt) for a in agents if a.n_steps]
    finish_times = sorted(a.finish_time for a in finished)

    # aggregate decision mix across every rider-step.
    counts = {a_: 0 for a_ in Action}
    total = 0
    for a in agents:
        for act, c in a.action_counts.items():
            counts[act] += c
            total += c

    m = {
        "n_riders": float(n),
        "finish_rate": len(finished) / n if n else 0.0,
        "drop_rate": sum(a.dropped for a in agents) / n if n else 0.0,
        "mean_speed_kmh": 3.6 * sum(speeds) / len(speeds) if speeds else 0.0,
        "winner_time_s": finish_times[0] if finish_times else float("nan"),
        "finish_spread_s": (finish_times[-1] - finish_times[0]
                            if len(finish_times) > 1 else 0.0),
        "drafted_share": (sum(a.n_sheltered for a in agents)
                          / max(1, sum(a.n_steps for a in agents))),
    }
    for act in Action:
        m[f"share_{act.value}"] = counts[act] / total if total else 0.0

    if winner is not None:
        m.update(
            winner_skill=winner.skill,
            winner_peak_speed_kmh=3.6 * winner.peak_speed,
            winner_drafted_share=winner.n_sheltered / max(1, winner.n_steps),
            winner_pull_share=(winner.action_counts[Action.PULL]
                               / max(1, winner.n_steps)),
            # v0.6 research question: did the team with the highest *initial
            # mean v_max* win? Rank teams by mean v_max (1 = fastest team) and
            # report the winning rider's team rank (1 = the fastest team won).
            winner_team_vmax_rank=float(_team_vmax_rank(agents, winner.team)),
        )
    return m


def _team_vmax_rank(agents, winner_team: int) -> int:
    """Rank (1 = highest) of ``winner_team`` among teams by mean v_max."""
    by_team: dict[int, list[float]] = {}
    for a in agents:
        by_team.setdefault(a.team, []).append(a.v_max)
    means = {t: sum(vs) / len(vs) for t, vs in by_team.items()}
    order = sorted(means, key=means.get, reverse=True)   # fastest team first
    return order.index(winner_team) + 1


#: metrics shown by the comparison dashboard, with display labels.
#: (drop_rate stays in the table/markdown output but not here: with the v0.4
#: W' speed cap riders fade rather than detonate, so hard drops are ~0 on a
#: flat race and the panel showed nothing.)
DASHBOARD_METRICS = [
    ("mean_speed_kmh", "mean field speed\n(km/h)"),
    ("winner_time_s", "winner's time\n(s)"),
    ("finish_spread_s", "finish spread\n(s)"),
    ("winner_pull_share", "winner's share of\nPULL work"),
    ("drafted_share", "time sheltered\n(share)"),
    ("winner_drafted_share", "winner's time\nsheltered (share)"),
]
