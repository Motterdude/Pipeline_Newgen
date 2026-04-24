"""Plot configuration parsing: axis specs, uncertainty, filenames.

Port of legacy L483-8470.  Consumes rows from ``plots_df`` (one per
plot entry in ``plots.toml``) and returns typed parameters ready for
the renderers.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..final_table._helpers import (
    _is_blank_cell,
    _to_float,
    _to_str_or_empty,
    norm_key,
    resolve_col,
)


# ── unit helpers ────────────────────────────────────────────────────

def _canon_unit_token(text: object) -> str:
    s = str(text).replace("﻿", "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s+", " ", s)
    s = s.replace("°", "").replace("º", "")
    s = s.replace("/", "_").replace("-", "_")
    if not s:
        return ""
    aliases = {
        "mbar": "mbar", "mbars": "mbar", "millibar": "mbar", "millibars": "mbar",
        "kpa": "kpa", "pa": "pa", "bar": "bar",
        "c": "c", "degc": "c", "celsius": "c",
    }
    return aliases.get(s, s)


def _unit_scale_to_base(unit: str) -> Optional[float]:
    scales = {"pa": 1.0, "mbar": 100.0, "kpa": 1000.0, "bar": 100000.0, "c": 1.0}
    return scales.get(_canon_unit_token(unit))


def _convert_unit_value(value: float, from_unit: str, to_unit: str) -> Optional[float]:
    from_scale = _unit_scale_to_base(from_unit)
    to_scale = _unit_scale_to_base(to_unit)
    if from_scale is None or to_scale is None:
        return None
    return float(value * from_scale / to_scale)


# ── axis spec parsing ───────────────────────────────────────────────

def _parse_axis_value(
    value: object,
    *,
    target_unit: Optional[str] = None,
    default: float = np.nan,
) -> float:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except Exception:
            return default
    text = str(value).replace("﻿", "").strip()
    if not text:
        return default
    if text.lower() in {"auto", "nan", "none", "off", "disabled", "n/a", "na"}:
        return default
    text_num = text.replace(",", ".")
    try:
        return float(text_num)
    except Exception:
        pass
    match = re.fullmatch(r"\s*([+-]?\d+(?:\.\d+)?)\s*([A-Za-z°º/_-]+)\s*", text_num)
    if not match:
        return default
    number = float(match.group(1))
    unit = _canon_unit_token(match.group(2))
    if not unit:
        return number
    if not target_unit:
        return number
    converted = _convert_unit_value(number, unit, target_unit)
    if converted is None:
        return default
    return converted


def _parse_axis_spec(
    min_v: object,
    max_v: object,
    step_v: object,
    *,
    target_unit: Optional[str] = None,
) -> Optional[Tuple[float, float, float]]:
    a = _parse_axis_value(min_v, target_unit=target_unit, default=np.nan)
    b = _parse_axis_value(max_v, target_unit=target_unit, default=np.nan)
    c = _parse_axis_value(step_v, target_unit=target_unit, default=np.nan)
    if not (np.isfinite(a) and np.isfinite(b) and np.isfinite(c)):
        return None
    if c <= 0:
        return None
    return (float(a), float(b), float(c))


def _parse_axis_limits(
    min_v: object,
    max_v: object,
    *,
    target_unit: Optional[str] = None,
) -> Optional[Tuple[float, float]]:
    a = _parse_axis_value(min_v, target_unit=target_unit, default=np.nan)
    b = _parse_axis_value(max_v, target_unit=target_unit, default=np.nan)
    if not (np.isfinite(a) and np.isfinite(b)):
        return None
    if float(b) <= float(a):
        return None
    return (float(a), float(b))


# ── row-level helpers ───────────────────────────────────────────────

def _parse_csv_list_ints(x: object) -> Optional[List[int]]:
    if _is_blank_cell(x):
        return None
    s = str(x).replace("﻿", "").strip()
    if not s:
        return None
    parts = [p.strip() for p in s.split(",") if p.strip()]
    out: List[int] = []
    for p in parts:
        if p == "":
            continue
        try:
            out.append(int(float(p.replace(",", "."))))
        except Exception:
            continue
    return out if out else None


def _row_enabled(v: object) -> bool:
    if v is None:
        return False
    try:
        if pd.isna(v):
            return False
    except Exception:
        pass
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    try:
        return bool(int(float(s)))
    except Exception:
        return False


def _mapping_unit_for_y_col(y_col: str, mappings: dict) -> Optional[str]:
    y_text = _to_str_or_empty(y_col)
    if not y_text:
        return None
    for _key_norm, spec in mappings.items():
        col_mean_req = str(spec.get("mean", "")).strip()
        if not col_mean_req:
            continue
        if norm_key(col_mean_req) == norm_key(y_text):
            unit = _to_str_or_empty(spec.get("unit", ""))
            return unit or None
    return None


# ── uncertainty / yerr helpers ──────────────────────────────────────

def _yerr_disabled_token(s: str) -> bool:
    t = str(s or "").strip().lower()
    return t in {"none", "off", "disable", "disabled", "0", "na", "n/a"}


def _plot_uncertainty_mode(v: object) -> str:
    text = _to_str_or_empty(v).lower()
    if not text or text in {"auto", "guess", "default"}:
        return "auto"
    if text in {"0", "false", "no", "off", "disable", "disabled", "none", "na", "n/a"}:
        return "off"
    return "on"


def _plot_uncertainty_flags(row: pd.Series) -> Tuple[bool, bool]:
    with_raw = _to_str_or_empty(row.get("with_uncertainty", "")).lower()
    without_raw = _to_str_or_empty(row.get("without_uncertainty", "")).lower()
    with_flag = with_raw in {"1", "true", "yes", "on", "y", "checked"}
    without_flag = without_raw in {"1", "true", "yes", "on", "y", "checked"}
    defined_vals = {"1", "0", "true", "false", "yes", "no", "on", "off", "y", "n", "checked", "unchecked"}
    with_defined = with_raw in defined_vals
    without_defined = without_raw in defined_vals

    if not with_defined and not without_defined:
        mode = _to_str_or_empty(row.get("show_uncertainty", "auto")).lower()
        if mode in {"off", "disable", "disabled", "none", "0", "false", "no", "na", "n/a"}:
            return False, True
        if mode in {"both", "all", "dual", "on_off"}:
            return True, True
        return True, False

    if not with_flag and not without_flag:
        return True, False
    return with_flag, without_flag


def _plot_uncertainty_variants(row: pd.Series) -> List[Tuple[str, str, bool]]:
    with_flag, without_flag = _plot_uncertainty_flags(row)
    both_selected = with_flag and without_flag
    variants: List[Tuple[str, str, bool]] = []
    if with_flag:
        variants.append(("with_uncertainty", "on", both_selected))
    if without_flag:
        variants.append(("without_uncertainty", "off", both_selected))
    if not variants:
        variants.append(("with_uncertainty", "on", False))
    return variants


def _decorate_plot_variant_output(
    filename: str, title: str, variant_key: str, dual_variant: bool
) -> Tuple[str, str]:
    if not dual_variant:
        return filename, title
    filename_suffix = "with_uncertainty" if variant_key == "with_uncertainty" else "without_uncertainty"
    title_suffix = "with uncertainty" if variant_key == "with_uncertainty" else "without uncertainty"
    fn = _strip_leading_raw_plot_name(filename)
    if fn.lower().endswith(".png"):
        fn = f"{fn[:-4]}_{filename_suffix}.png"
    elif fn:
        fn = f"{fn}_{filename_suffix}"
    tt = _strip_leading_raw_plot_name(title)
    if tt:
        tt = f"{tt} | {title_suffix}"
    return fn, tt


def _prefix_from_key_norm(key_norm: str) -> str:
    if key_norm == "power_kw":
        return "P_kw"
    if key_norm == "fuel_kgh":
        return "Consumo_kg_h"
    if key_norm == "lhv_kj_kg":
        return "LHV_kJ_kg"
    emission_prefixes: Dict[str, str] = {
        "co_pct": "CO_pct", "co2_pct": "CO2_pct", "o2_pct": "O2_pct",
        "nox_ppm": "NOx_ppm", "no_ppm": "NO_ppm", "thc_ppm": "THC_ppm",
    }
    if key_norm in emission_prefixes:
        return emission_prefixes[key_norm]
    return key_norm.upper()


def _guess_plot_uncertainty_col(
    out_df: pd.DataFrame, y_col: str, mappings: dict
) -> Optional[str]:
    candidates: List[str] = []
    direct = f"U_{y_col}"
    if direct not in candidates:
        candidates.append(direct)
    for key_norm, spec in mappings.items():
        col_mean_req = str(spec.get("mean", "")).strip()
        if not col_mean_req:
            continue
        try:
            mapped_mean = resolve_col(out_df, col_mean_req)
        except Exception:
            continue
        if mapped_mean == y_col:
            cand = f"U_{_prefix_from_key_norm(key_norm)}"
            if cand not in candidates:
                candidates.append(cand)
    for cand in candidates:
        if cand not in out_df.columns:
            continue
        vals = pd.to_numeric(out_df[cand], errors="coerce")
        if vals.notna().any():
            return cand
    return None


def _resolve_plot_yerr_col(
    out_df: pd.DataFrame,
    row: pd.Series,
    *,
    y_col: str,
    mappings: dict,
    plot_label: str,
) -> Optional[str]:
    yerr_req = _to_str_or_empty(row.get("yerr_col", ""))
    uncertainty_mode = _plot_uncertainty_mode(row.get("show_uncertainty", "auto"))
    if uncertainty_mode == "off":
        return None
    if yerr_req and not _yerr_disabled_token(yerr_req):
        try:
            return resolve_col(out_df, yerr_req)
        except Exception:
            print(f"[INFO] Plot '{plot_label}': yerr_col '{yerr_req}' nao encontrado. Vou tentar fallback.")
    guessed = _guess_plot_uncertainty_col(out_df, y_col, mappings)
    if guessed:
        print(f"[INFO] Plot '{plot_label}': usando '{guessed}' como incerteza final.")
        return guessed
    if yerr_req and not _yerr_disabled_token(yerr_req):
        print(f"[INFO] Plot '{plot_label}': fallback sem yerr, porque '{yerr_req}' nao existe no output.")
    return None


# ── filename / title helpers ────────────────────────────────────────

def _strip_leading_raw_plot_name(value: object) -> str:
    text = _to_str_or_empty(value)
    if text.lower().startswith("raw_"):
        return text[4:]
    return text


def _safe_name(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]+", "_", str(name))
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _derive_filename_for_expansion(template: str, y_col: str) -> str:
    t = _strip_leading_raw_plot_name(template)
    if not t:
        return f"kibox_{_safe_name(y_col)}_vs_power_all.png"
    if "{y}" in t:
        return t.replace("{y}", _safe_name(y_col))
    if t.lower().endswith(".png"):
        stem = t[:-4]
        return f"{stem}_{_safe_name(y_col)}.png"
    return f"{t}_{_safe_name(y_col)}.png"


def _derive_title_for_expansion(template: str, x_col: str, y_col: str) -> str:
    t = _strip_leading_raw_plot_name(template)
    if not t:
        return f"{y_col} vs {x_col} (all fuels)"
    if "{y}" in t or "{x}" in t:
        return t.replace("{y}", y_col).replace("{x}", x_col)
    return t


# ── x-axis resolution (simplified, no mestrado mode) ───────────────

def _resolve_plot_x_request(x_col_req: str) -> Tuple[str, bool]:
    req = _to_str_or_empty(x_col_req)
    return (req if req else "Load_kW"), False


def _runtime_plot_x_label(
    x_label: str,
    x_col_base: str,
    x_col_resolved: str,
    mestrado_override: bool,
) -> str:
    label = _to_str_or_empty(x_label)
    return label if label else x_col_resolved


# ── shared y-limits for uncertainty variants ────────────────────────

def _shared_plot_y_limits_for_variants(
    df: pd.DataFrame,
    *,
    x_col: str,
    y_col: str,
    variant_yerr_cols: List[Optional[str]],
    fuels_override: Optional[List[int]] = None,
    series_col: Optional[str] = None,
    y_tol_plus: object = 0.0,
    y_tol_minus: object = 0.0,
) -> Optional[Tuple[float, float]]:
    from .fuel_groups import series_fuel_plot_groups

    values: List[float] = []
    for yerr_col in variant_yerr_cols:
        for _, d in series_fuel_plot_groups(df, fuels_override=fuels_override, series_col=series_col):
            work = d.copy()
            work[x_col] = pd.to_numeric(work[x_col], errors="coerce")
            work[y_col] = pd.to_numeric(work[y_col], errors="coerce")
            if yerr_col:
                work[yerr_col] = pd.to_numeric(work[yerr_col], errors="coerce")
                work = work.dropna(subset=[x_col, y_col, yerr_col]).sort_values(x_col)
            else:
                work = work.dropna(subset=[x_col, y_col]).sort_values(x_col)
            if work.empty:
                continue
            y = pd.to_numeric(work[y_col], errors="coerce")
            values.extend(float(v) for v in y.dropna().tolist() if np.isfinite(v))
            if yerr_col:
                yerr = pd.to_numeric(work[yerr_col], errors="coerce").abs()
                low = y - yerr
                high = y + yerr
                values.extend(float(v) for v in low.dropna().tolist() if np.isfinite(v))
                values.extend(float(v) for v in high.dropna().tolist() if np.isfinite(v))

    from .renderers import _normalize_tol_value

    tp = _normalize_tol_value(y_tol_plus)
    tm = _normalize_tol_value(y_tol_minus)
    if tp > 0:
        values.append(float(tp))
    if tm > 0:
        values.append(float(-tm))

    finite_values = [float(v) for v in values if np.isfinite(v)]
    if not finite_values:
        return None
    ymin = min(finite_values)
    ymax = max(finite_values)
    if ymax <= ymin:
        span_ref = max(abs(ymax), abs(ymin), 1.0)
        pad = span_ref * 0.05
    else:
        pad = (ymax - ymin) * 0.05
    return ymin - pad, ymax + pad
