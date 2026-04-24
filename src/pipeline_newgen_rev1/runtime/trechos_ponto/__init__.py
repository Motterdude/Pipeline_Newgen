"""Trechos/ponto stats subpackage: native port of ``compute_trechos_stats``
and ``compute_ponto_stats`` from legacy ``nanum_pipeline_29.py``.

Consumed by ``runtime/stages/compute_trechos_ponto.py``.
"""
from __future__ import annotations

from .constants import (
    B_ETANOL_COL_CANDIDATES,
    DT_S,
    GROUP_COLS_PONTO,
    GROUP_COLS_TRECHOS,
    MIN_SAMPLES_PER_WINDOW,
)
from .core import compute_ponto_stats, compute_trechos_stats
from .helpers import (
    find_b_etanol_col,
    get_resolution_for_key,
    has_instrument_key,
    normalize_repeated_stat_tokens,
    res_to_std,
)

__all__ = [
    "B_ETANOL_COL_CANDIDATES",
    "DT_S",
    "GROUP_COLS_PONTO",
    "GROUP_COLS_TRECHOS",
    "MIN_SAMPLES_PER_WINDOW",
    "compute_ponto_stats",
    "compute_trechos_stats",
    "find_b_etanol_col",
    "get_resolution_for_key",
    "has_instrument_key",
    "normalize_repeated_stat_tokens",
    "res_to_std",
]
