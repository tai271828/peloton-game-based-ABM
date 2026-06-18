"""Parallel batch runner — many races across worker processes.

Sensitivity analysis needs thousands of races; a single core does ~2 races/s,
so v0.5 adds this thin multiprocessing layer (a gap in all earlier versions).
Each config is a plain dict of :class:`~peloton.model.RaceModel` kwargs (the
seed travels inside the config, so results are deterministic and order-
preserving regardless of scheduling). Returns one
:func:`~peloton.analysis.metrics.race_metrics` dict per config.
"""

from __future__ import annotations

import os
from multiprocessing import Pool

from peloton.analysis.metrics import race_metrics
from peloton.model import RaceModel


def run_one(config: dict) -> dict:
    """Run a single race config to completion and summarise it."""
    cfg = {**config, "collect": False}
    m = RaceModel(**cfg)
    m.run()
    return race_metrics(m)


def run_many(configs: list[dict], workers: int | None = None) -> list[dict]:
    """Run every config; results are in input order.

    ``workers=1`` (or a single config) runs serially in-process — useful in
    tests and avoids pool overhead for tiny batches.
    """
    workers = workers or max(1, (os.cpu_count() or 2) - 1)
    if workers == 1 or len(configs) <= 1:
        return [run_one(c) for c in configs]
    chunk = max(1, len(configs) // (workers * 8))
    with Pool(workers) as pool:
        return pool.map(run_one, configs, chunksize=chunk)
