"""Evolutionary dynamics — race-to-race selection on cooperation tendency.

The course brief (and the 2011 Hoenigman et al. paper) frame cooperation as
something riders *learn*: v0.1 had this experiment, v0.2–v0.4 dropped it.
v0.5 re-implements it on the current physics (v0.1's result predates the W′
cap and 2-D positioning, so it is strictly a result from a different model).

Mechanism (deliberately the simplest selection dynamic):

* a population of per-rider ``p_coop`` values plays one ``public_goods`` race
  per generation (per-rider parameters via the v0.5 ``strategy_params`` list);
* the better-finishing half survives; the worse half is replaced by mutated
  copies of the survivors (``p' = clip(p + N(0, mut_sd))``);
* track the population mean across generations.

The complementary *stability* evidence — does the evolved mean sit where
unilateral deviations stop paying? — comes from the deviation harness
(``peloton.analysis.deviation``), giving two independent estimates of the
same interior equilibrium.
"""

from __future__ import annotations

import os
import random
from multiprocessing import Pool


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def evolve(generations: int = 60, n_riders: int = 48, n_teams: int = 8,
           seed: int = 0, mut_sd: float = 0.05) -> dict:
    """One evolutionary run; returns the p_coop trajectory.

    Returns dict with ``mean`` (per-generation population mean), ``sd``
    (population spread), and ``final_pop`` (last generation's p_coop list).
    """
    from peloton.model import RaceModel       # local: keeps workers cheap

    rng = random.Random(seed)
    pop = [rng.random() for _ in range(n_riders)]
    mean_traj, sd_traj = [], []

    for _ in range(generations):
        sp = [{"p_coop": pc} for pc in pop]
        m = RaceModel(n_riders=n_riders, n_teams=n_teams,
                      strategy="public_goods", strategy_params=sp,
                      seed=rng.randrange(2**31), collect=False)
        m.run()
        ranked = sorted(m.agents, key=lambda a: a.finish_rank)
        survivors = [a.strategy.p_coop for a in ranked[: n_riders // 2]]
        children = [_clip01(pc + rng.gauss(0.0, mut_sd)) for pc in survivors]
        pop = survivors + children
        n = len(pop)
        mu = sum(pop) / n
        mean_traj.append(mu)
        sd_traj.append((sum((x - mu) ** 2 for x in pop) / n) ** 0.5)

    return {"mean": mean_traj, "sd": sd_traj, "final_pop": pop, "seed": seed}


def _evolve_job(job: dict) -> dict:
    return evolve(**job)


def evolve_many(n_runs: int = 5, workers: int | None = None,
                **kw) -> list[dict]:
    """Independent evolutionary runs (different seeds) in parallel."""
    jobs = [{**kw, "seed": s} for s in range(n_runs)]
    workers = workers or max(1, (os.cpu_count() or 2) - 1)
    if workers == 1 or n_runs == 1:
        return [_evolve_job(j) for j in jobs]
    with Pool(min(workers, n_runs)) as pool:
        return pool.map(_evolve_job, jobs)
