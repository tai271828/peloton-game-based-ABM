"""Analysis toolkit: standard metrics, strategy comparison, data calibration."""

from peloton.analysis.metrics import race_metrics
from peloton.analysis.compare import compare, summarize

__all__ = ["race_metrics", "compare", "summarize"]
