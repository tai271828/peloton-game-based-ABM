"""Animate a peloton race on the stadium track.

Runs a :class:`~peloton.model.RaceModel`, records every step's rider positions,
and renders them as moving dots around the discorectangle track. Riders are
coloured by team; pullers (taking the wind) are ringed, captains drawn as
stars, dropped riders greyed out. Saves to ``figures/race_<strategy>.mp4``
(falling back to ``.gif`` when ffmpeg is unavailable).

Usage (any auto-discovered strategy works — no hard-coded list)::

    python -m peloton.viz.animate --strategy discrete_choice
    python -m peloton.viz.animate --strategy lead_out --riders 56 --seed 3
"""

from __future__ import annotations

import argparse
import os

import matplotlib
matplotlib.use("Agg")  # headless: render to file, no display needed
import matplotlib.pyplot as plt
from matplotlib import animation
from matplotlib.lines import Line2D

from peloton import RaceModel, Role
from peloton.actions import Action
from peloton.strategies import available

FIG_DIR = "figures"


def record_race(model: RaceModel, max_steps: int, sample_every: int) -> list[dict]:
    """Run the model, capturing a light snapshot of state every few steps."""
    frames: list[dict] = []

    def snap():
        frames.append(dict(
            x=[], y=[], colors=[], pulling=[], dropped=[], captain=[],
            step=model.steps,
            lead=max(a.distance for a in model.agents),
            packs=model._n_packs,
        ))
        f = frames[-1]
        for a in model.agents:
            xx, yy = model.track.xy(a.s, a.lane)
            f["x"].append(xx)
            f["y"].append(yy)
            f["colors"].append(a.team)
            f["pulling"].append(a.action is Action.PULL and not a.finished)
            f["dropped"].append(a.dropped)
            f["captain"].append(a.role is Role.CAPTAIN)

    snap()
    while model.n_finished < len(model.agents) and model.steps < max_steps:
        model.step()
        if model.steps % sample_every == 0:
            snap()
    snap()
    return frames


def animate(strategy="lead_out", n_riders=48, n_teams=8, seed=1,
            max_steps=4000, sample_every=2, fps=25, out=None,
            strategy_params=None):
    model = RaceModel(n_riders=n_riders, n_teams=n_teams, strategy=strategy,
                      strategy_params=strategy_params, seed=seed,
                      collect=False)
    frames = record_race(model, max_steps, sample_every)

    track = model.track
    xs, ys = track.outline(n=600)
    inner_x, inner_y = track.outline(n=600, lane=model.lane_hi)
    outer_x, outer_y = track.outline(n=600, lane=model.lane_lo)

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(xs, ys, color="0.7", lw=1, ls="--", zorder=1)
    ax.plot(inner_x, inner_y, color="0.4", lw=1.5, zorder=1)
    ax.plot(outer_x, outer_y, color="0.4", lw=1.5, zorder=1)

    # finish line (start/finish at s = 0).
    fx0, fy0 = track.xy(0.0, model.lane_lo)
    fx1, fy1 = track.xy(0.0, model.lane_hi)
    ax.plot([fx0, fx1], [fy0, fy1], color="crimson", lw=2.5, zorder=2)

    cmap = plt.get_cmap("tab10")
    riders = ax.scatter([], [], s=55, zorder=4, edgecolors="none")
    rings = ax.scatter([], [], s=150, facecolors="none",
                       edgecolors="black", linewidths=1.0, zorder=5)
    # captains drawn as larger stars with a dark edge, so the trains are readable.
    captains = ax.scatter([], [], s=240, marker="*", zorder=6,
                          edgecolors="black", linewidths=1.0)
    title = ax.set_title("")

    ax.set_aspect("equal")
    pad = 25
    ax.set_xlim(min(outer_x) - pad, max(outer_x) + pad)
    ax.set_ylim(min(outer_y) - pad, max(outer_y) + pad)
    ax.axis("off")
    legend = [Line2D([0], [0], marker="*", color="w", label="captain",
                     markerfacecolor="0.5", markeredgecolor="black", markersize=15),
              Line2D([0], [0], marker="o", color="w", label="puller (in wind)",
                     markerfacecolor="0.6", markeredgecolor="black", markersize=10),
              Line2D([0], [0], marker="o", color="w", label="dropped",
                     markerfacecolor="0.85", markersize=8)]
    ax.legend(handles=legend, loc="upper right", fontsize=8, framealpha=0.9)

    total_laps = model.params["n_laps"]

    def update(i):
        f = frames[i]
        xy = list(zip(f["x"], f["y"]))
        base = [cmap(c % 10) for c in f["colors"]]
        face = [(0.8, 0.8, 0.8, 1.0) if d else col
                for col, d in zip(base, f["dropped"])]
        # non-captains in the main scatter, captains in the star scatter.
        riders.set_offsets([p for p, cap in zip(xy, f["captain"]) if not cap])
        riders.set_facecolors([c for c, cap in zip(face, f["captain"]) if not cap])
        cap_xy = [p for p, cap in zip(xy, f["captain"]) if cap]
        captains.set_offsets(cap_xy if cap_xy else [(None, None)])
        captains.set_facecolors([c for c, cap in zip(face, f["captain"]) if cap]
                                or [(0, 0, 0, 0)])
        ring_xy = [p for p, pull in zip(xy, f["pulling"]) if pull]
        rings.set_offsets(ring_xy if ring_xy else [(None, None)])
        lap = min(total_laps, int(f["lead"] // track.length) + 1)
        title.set_text(f"{strategy} — step {f['step']} | lap {lap}/{total_laps} "
                       f"| packs {f['packs']}")
        return riders, rings, captains, title

    anim = animation.FuncAnimation(fig, update, frames=len(frames),
                                   interval=1000 / fps, blit=False)

    os.makedirs(FIG_DIR, exist_ok=True)
    if out is None:
        out = os.path.join(FIG_DIR, f"race_{strategy}")
    saved = _save(anim, out, fps)
    plt.close(fig)
    print(f"[animate] {strategy}: {len(frames)} frames -> {saved}")
    return saved


def _save(anim, out_base: str, fps: int) -> str:
    """Try mp4 (ffmpeg); fall back to gif (pillow)."""
    try:
        path = out_base + ".mp4"
        anim.save(path, writer=animation.FFMpegWriter(fps=fps, bitrate=1800))
        return path
    except Exception as exc:  # ffmpeg missing / failed
        print(f"[animate] mp4 unavailable ({exc}); writing gif")
        path = out_base + ".gif"
        anim.save(path, writer=animation.PillowWriter(fps=fps))
        return path


def main():
    ap = argparse.ArgumentParser(description="Animate a peloton race.")
    ap.add_argument("--strategy", default="lead_out", choices=available(),
                    help="any auto-discovered strategy")
    ap.add_argument("--riders", type=int, default=48)
    ap.add_argument("--teams", type=int, default=8)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--sample-every", type=int, default=2)
    ap.add_argument("--fps", type=int, default=25)
    args = ap.parse_args()
    animate(strategy=args.strategy, n_riders=args.riders, n_teams=args.teams,
            seed=args.seed, sample_every=args.sample_every, fps=args.fps)


if __name__ == "__main__":
    main()
