from __future__ import annotations

from typing import List, Tuple


RUNTIME_AGGREGATION_LOAD = "load"
RUNTIME_AGGREGATION_SWEEP = "sweep"
DEFAULT_SWEEP_KEY = "lambda"
SWEEP_VALUE_COL = "Sweep_Value"
DEFAULT_SWEEP_BIN_TOL = 0.015

SWEEP_AXIS_LABELS = {
    "lambda": "Lambda",
    "afr": "AFR",
    "egr": "EGR (%)",
    "soi": "SOI",
    "spark": "Spark timing",
    "rail": "Rail pressure",
    "boost": "Boost",
}

SWEEP_FILENAME_PATTERNS: List[Tuple[str, str]] = [
    ("lambda", r"(?:^|[_-])(?:lambda|lam)(?:[_-]+)(-?\d+(?:[.,]\d+)?)"),
    ("afr", r"(?:^|[_-])afr(?:[_-]+)(-?\d+(?:[.,]\d+)?)"),
    ("egr", r"(?:^|[_-])egr(?:[_-]+)(-?\d+(?:[.,]\d+)?)"),
    ("soi", r"(?:^|[_-])soi(?:[_-]+)(-?\d+(?:[.,]\d+)?)"),
    ("spark", r"(?:^|[_-])(?:spark|ign|ignition|advance|adv)(?:[_-]+)(-?\d+(?:[.,]\d+)?)"),
    ("rail", r"(?:^|[_-])rail(?:[_-]+)(-?\d+(?:[.,]\d+)?)"),
    ("boost", r"(?:^|[_-])boost(?:[_-]+)(-?\d+(?:[.,]\d+)?)"),
]

