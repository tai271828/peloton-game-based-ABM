# Calibration data

`stylized_facts.csv` holds the **target observables** the calibration pipeline
(`python -m peloton.analysis.calibrate`) fits the `discrete_choice` strategy
against. Columns:

| column | meaning |
|---|---|
| `observable` | a key produced by `peloton.analysis.metrics.race_metrics` |
| `target` | the observed real-world value |
| `weight` | relative importance in the fit objective |
| `source` | where the number comes from |

## Provenance — read this before citing results

The shipped values are **stylized facts**: order-of-magnitude figures assembled
from public race reporting and the modelling literature (bunch speeds in pro
flat-race finales ~45–50 km/h; field-sprint peaks ~65–75 km/h; sprint winners
riding sheltered behind a train; a few percent of the field distanced in the
finale). They are *illustrative defaults to demonstrate the pipeline*, *not* a
curated dataset — we did not scrape or licence race telemetry for this
prototype.

**To interpret real data, replace this file with your own measurements** —
e.g. per-stage speeds from race reports, broadcast telemetry, or Strava/
ProCyclingStats aggregates — keeping the same columns. Any metric emitted by
`race_metrics` can be used as an `observable` (including the per-action
decision shares `share_pull`, `share_draft`, … if you have behavioural data).
The calibration machinery does not change.

## Referent system (v0.5 clarification)

The simulated race is ~4 km on a 1.3 km closed circuit (~5 minutes) — a
**criterium / track-race** scale, *not* a 160–250 km road stage. Speed and
sprint targets above are defensible at both scales (crit and road-finale
speeds overlap), but hour-scale phenomena (long-range breakaways, attrition,
feed-zone energetics) are out of referent and must not be calibrated against.
Extending the course (laps are free) and recalibrating is the road-race path;
see docs/validation.md.
