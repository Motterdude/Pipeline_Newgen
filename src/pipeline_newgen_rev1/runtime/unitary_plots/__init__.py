"""Unitary-plots subpackage: native port of the legacy unitary plot
generation from ``nanum_pipeline_29.py``.

Consumed by ``runtime/stages/run_unitary_plots.py``.
"""
from __future__ import annotations

from .dispatch import make_plots_from_config_with_summary

__all__ = [
    "make_plots_from_config_with_summary",
]
