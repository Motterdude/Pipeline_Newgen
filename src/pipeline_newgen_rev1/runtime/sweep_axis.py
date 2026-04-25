"""Sweep axis resolution and filename/title rewriting for plots.

Port of legacy nanum_pipeline_30.py L8668-8795.
All functions are pure — no global state.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

from ..ui.runtime_preflight.constants import (
    SWEEP_AXIS_LABELS,
    SWEEP_BIN_VALUE_COL,
    SWEEP_VALUE_COL,
)


def _to_str_or_empty(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _norm_key(s: str) -> str:
    return s.strip().lower().replace(" ", "_")


def _safe_name(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]+", "_", str(name))
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _sweep_axis_label(sweep_key: str) -> str:
    return SWEEP_AXIS_LABELS.get(sweep_key, sweep_key or "Sweep")


def _matches_load_request(x_col_req: str, sweep_active: bool) -> bool:
    if not sweep_active:
        return False
    req = _to_str_or_empty(x_col_req)
    return (not req) or _norm_key(req) == _norm_key("Load_kW")


def sweep_axis_label_for_col(
    x_col: str,
    *,
    sweep_x_col: str,
    sweep_key: str,
) -> str:
    col = _to_str_or_empty(x_col)
    col_norm = _norm_key(col) if col else ""
    if not col or col_norm in {_norm_key(SWEEP_VALUE_COL), _norm_key(SWEEP_BIN_VALUE_COL)}:
        source_col = _to_str_or_empty(sweep_x_col)
        source_norm = _norm_key(source_col)
        if source_col and source_norm not in {
            _norm_key(SWEEP_VALUE_COL),
            _norm_key(SWEEP_BIN_VALUE_COL),
        }:
            pretty = re.sub(r"(?i)_mean_of_windows$", "", source_col)
            pretty = re.sub(r"(?i)_sd_of_windows$", "", pretty)
            return pretty if pretty else source_col
        return _sweep_axis_label(sweep_key)
    pretty = re.sub(r"(?i)_mean_of_windows$", "", col)
    pretty = re.sub(r"(?i)_sd_of_windows$", "", pretty)
    return pretty if pretty else col


def sweep_axis_token_for_col(
    x_col: str,
    *,
    sweep_x_col: str,
    sweep_key: str,
) -> str:
    label = sweep_axis_label_for_col(x_col, sweep_x_col=sweep_x_col, sweep_key=sweep_key)
    token = _safe_name(label)
    if token:
        return token
    col = _to_str_or_empty(x_col)
    return _safe_name(col) if col else _safe_name(sweep_key)


def resolve_plot_x_for_sweep(
    x_col_req: str,
    *,
    sweep_active: bool,
    sweep_x_col: str,
    sweep_effective_x_col: str,
) -> Tuple[str, bool]:
    req = _to_str_or_empty(x_col_req)
    if _matches_load_request(req, sweep_active):
        return sweep_effective_x_col, True
    if sweep_active and _norm_key(req) in {
        _norm_key(sweep_x_col),
        _norm_key(SWEEP_BIN_VALUE_COL),
    }:
        return sweep_effective_x_col, True
    return (req if req else "Load_kW"), False


def resolve_plot_x_label_for_sweep(
    x_label: str,
    x_col_base: str,
    x_col_resolved: str,
    *,
    sweep_active: bool,
    sweep_x_col: str,
    sweep_effective_x_col: str,
    sweep_axis_label: str,
) -> str:
    label = _to_str_or_empty(x_label)
    if sweep_active and _norm_key(x_col_resolved) in {
        _norm_key(sweep_x_col),
        _norm_key(sweep_effective_x_col),
    }:
        label_norm = _norm_key(label) if label else ""
        auto_labels = {
            _norm_key(x_col_base),
            _norm_key(x_col_resolved),
            _norm_key("Load_kW"),
            _norm_key("Carga (kW)"),
            _norm_key("Power (kW)"),
            _norm_key("Power"),
            _norm_key("Potencia (kW)"),
            _norm_key(SWEEP_VALUE_COL),
            _norm_key(SWEEP_BIN_VALUE_COL),
        }
        if not label or label_norm in auto_labels:
            return sweep_axis_label
    return label if label else x_col_resolved


def resolve_plot_fixed_x_for_sweep(
    x_col_req: str,
    fixed_x: Optional[Tuple[float, float, float]],
    *,
    sweep_active: bool,
    sweep_x_col: str,
) -> Optional[Tuple[float, float, float]]:
    if _matches_load_request(x_col_req, sweep_active):
        return None
    if sweep_active and _norm_key(x_col_req) in {
        _norm_key(sweep_x_col),
        _norm_key(SWEEP_BIN_VALUE_COL),
    }:
        return None
    return fixed_x


def rewrite_plot_filename_title(
    filename: str,
    title: str,
    *,
    x_col_req: str,
    x_col_resolved: str,
    sweep_active: bool,
    sweep_x_col: str,
    sweep_effective_x_col: str,
    sweep_axis_token: str,
    sweep_axis_label: str,
) -> Tuple[str, str]:
    if not sweep_active:
        return filename, title
    resolved_norm = _norm_key(x_col_resolved)
    if resolved_norm not in {_norm_key(sweep_x_col), _norm_key(sweep_effective_x_col)}:
        return filename, title
    req_is_load = _matches_load_request(x_col_req, sweep_active)
    req_is_sweep = _norm_key(x_col_req) in {
        _norm_key(sweep_x_col),
        _norm_key(SWEEP_BIN_VALUE_COL),
    }
    if not req_is_load and not req_is_sweep:
        return filename, title

    out_fn = filename
    out_tt = title
    if out_fn:
        out_fn = re.sub(r"(?i)vs_power", f"vs_{sweep_axis_token}", out_fn)
        out_fn = re.sub(r"(?i)vs_load", f"vs_{sweep_axis_token}", out_fn)
        out_fn = re.sub(r"(?i)load_k_w", sweep_axis_token, out_fn)
        out_fn = re.sub(r"(?i)load_kw", sweep_axis_token, out_fn)
    if out_tt:
        out_tt = re.sub(r"(?i)\bvs load\b", f"vs {sweep_axis_label}", out_tt)
        out_tt = re.sub(r"(?i)\bvs power\b", f"vs {sweep_axis_label}", out_tt)
        out_tt = re.sub(r"(?i)\bload_kW\b", sweep_axis_label, out_tt)
        out_tt = re.sub(r"(?i)\bload\b", sweep_axis_label, out_tt)
    return out_fn, out_tt
