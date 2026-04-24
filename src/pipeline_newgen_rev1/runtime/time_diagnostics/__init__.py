"""Time-diagnostics subpackage: native port of `build_time_diagnostics`,
`summarize_time_diagnostics`, `plot_time_delta_by_file`, and
`plot_time_delta_all_samples` from the legacy `nanum_pipeline_29.py`.

Consumed by `runtime/stages/run_time_diagnostics.py`.
"""

from __future__ import annotations

from .constants import (
    DEFAULT_MAX_ACT_CONTROL_ERROR_C,
    DEFAULT_MAX_DELTA_BETWEEN_SAMPLES_MS,
    DEFAULT_MAX_ECT_CONTROL_ERROR_C,
    TIME_DELTA_ERROR_THRESHOLD_S,
    TIME_DELTA_PLOT_YMAX_S,
    TIME_DELTA_PLOT_YMIN_S,
    TIME_DELTA_PLOT_YSTEP_S,
    TIME_DIAG_FILE_SCATTER_MAX_POINTS,
    TIME_DIAG_PLOT_DPI,
)
from .core import build_time_diagnostics
from .plots import plot_time_delta_all_samples, plot_time_delta_by_file
from .summary import summarize_time_diagnostics


__all__ = [
    "build_time_diagnostics",
    "summarize_time_diagnostics",
    "plot_time_delta_by_file",
    "plot_time_delta_all_samples",
    "TIME_DELTA_ERROR_THRESHOLD_S",
    "DEFAULT_MAX_DELTA_BETWEEN_SAMPLES_MS",
    "DEFAULT_MAX_ACT_CONTROL_ERROR_C",
    "DEFAULT_MAX_ECT_CONTROL_ERROR_C",
    "TIME_DELTA_PLOT_YMIN_S",
    "TIME_DELTA_PLOT_YMAX_S",
    "TIME_DELTA_PLOT_YSTEP_S",
    "TIME_DIAG_PLOT_DPI",
    "TIME_DIAG_FILE_SCATTER_MAX_POINTS",
]
