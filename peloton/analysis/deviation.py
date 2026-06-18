"""Empirical equilibrium analysis via unilateral deviation (EGTA-style).

Earlier versions *asserted* equilibria ("Nash = defect", "mixed ESS"); v0.5
measures them. The instrument is the oldest one in game theory: hold the
whole field at a strategy parameter value, let **one focal rider** deviate,
and ask whether the deviation pays.

* If the focal rider's payoff is monotone in the deviation parameter for
  *every* field value, the boundary strategy is **dominant** and the
  symmetric Nash equilibrium sits at that boundary (public-goods: defect).
* If the best response crosses the diagonal (best deviation ≈ field value),
  that crossing is an **empirical interior mixed equilibrium** (Hawk–Dove).

Design notes for fairness/power:

- payoff = focal rider's normalised finish rank (0 = winner; lower = better);
- the **skill vector is frozen per seed** and the focal rider always has
  skill exactly 1.0 mid-grid, so across deviation arms the *only* difference
  is the focal rider's parameter (common random numbers → paired analysis);
- per-rider parameters use the v0.5 ``strategy_params`` list support;
- races run across worker processes (``peloton.analysis.batch`` pool sizing).
"""

from __future__ import annotations

import os
import random
from multiprocessing import Pool

from peloton.model import RaceModel
from peloton.params import DEFAULT_PARAMS


def _skills(n_riders: int, seed: int) -> list[float]:
    """The skill draw RaceModel would make, frozen so all arms share it."""
    rng = random.Random(seed)
    p = DEFAULT_PARAMS
    sk = [max(p["skill_min"], min(p["skill_max"],
              rng.gauss(p["skill_mean"], p["skill_sd"])))
          for _ in range(n_riders)]
    sk[n_riders // 2] = 1.0          # focal rider: fixed average skill
    return sk


def _focal_rank(job: dict) -> float:
    """Worker: run one race, return the focal rider's normalised rank."""
    n_riders = job["n_riders"]
    focal = n_riders // 2
    sp = [{job["param"]: job["field_value"]} for _ in range(n_riders)]
    sp[focal] = {job["param"]: job["dev_value"]}
    m = RaceModel(n_riders=n_riders, n_teams=job["n_teams"],
                  strategy=job["strategy"], strategy_params=sp,
                  skills=_skills(n_riders, job["seed"]),
                  seed=job["seed"], collect=False)
    m.run()
    rider = sorted(m.agents, key=lambda a: a.unique_id)[focal]
    return rider.finish_rank / (n_riders - 1)


def deviation_payoffs(strategy: str, param: str, field_values, dev_values,
                      seeds, n_riders: int = 48, n_teams: int = 8,
                      workers: int | None = None
                      ) -> dict[float, dict[float, list[float]]]:
    """{field_value: {dev_value: [per-seed focal payoffs]}} — all in parallel."""
    jobs = [dict(strategy=strategy, param=param, field_value=float(fv),
                 dev_value=float(dv), seed=int(s), n_riders=n_riders,
                 n_teams=n_teams)
            for fv in field_values for dv in dev_values for s in seeds]
    workers = workers or max(1, (os.cpu_count() or 2) - 1)
    if workers == 1:
        ranks = [_focal_rank(j) for j in jobs]
    else:
        with Pool(workers) as pool:
            ranks = pool.map(_focal_rank, jobs,
                             chunksize=max(1, len(jobs) // (workers * 8)))
    out: dict[float, dict[float, list[float]]] = {}
    for job, r in zip(jobs, ranks):
        out.setdefault(job["field_value"], {}).setdefault(
            job["dev_value"], []).append(r)
    return out


def best_responses(curves: dict[float, dict[float, list[float]]]
                   ) -> list[tuple[float, float]]:
    """(field_value, payoff-minimising deviation) per field value."""
    res = []
    for fv, by_dev in sorted(curves.items()):
        means = {dv: sum(v) / len(v) for dv, v in by_dev.items()}
        res.append((fv, min(means, key=means.get)))
    return res
