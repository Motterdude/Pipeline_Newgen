"""compare_iteracoes: native port of the BL×ADTV comparison pipeline.

Processing:
  compute_compare_iteracoes() → CompareResult (delta tables + series frames)

Plotting:
  plot_compare_absolute() → absolute-value PNGs
  plot_compare_delta_pct() → delta-percentage PNGs
"""
from .core import CompareResult, compute_compare_iteracoes
from .plot_absolute import plot_compare_absolute
from .plot_delta import plot_compare_delta_pct
from .specs import (
    COMPARE_ITER_METRIC_SPECS,
    COMPARE_ITER_METRIC_SPECS_BY_ID,
    COMPARE_ITER_SERIES_META,
    K_COVERAGE,
    build_series_meta_from_catalog,
    compare_iter_pair_context,
)

__all__ = [
    "CompareResult",
    "COMPARE_ITER_METRIC_SPECS",
    "COMPARE_ITER_METRIC_SPECS_BY_ID",
    "COMPARE_ITER_SERIES_META",
    "K_COVERAGE",
    "build_series_meta_from_catalog",
    "compare_iter_pair_context",
    "compute_compare_iteracoes",
    "plot_compare_absolute",
    "plot_compare_delta_pct",
]
