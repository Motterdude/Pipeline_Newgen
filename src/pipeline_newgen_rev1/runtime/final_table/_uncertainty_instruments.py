"""Mapping-driven uncertainty workflow: uA/uB/uc/U from instruments + temperature combining."""
from __future__ import annotations

import re
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ._helpers import _is_blank_cell, _to_float, _to_str_or_empty, norm_key, resolve_col
from .constants import K_COVERAGE, rect_to_std, res_to_std


def _prefix_from_key_norm(key_norm: str) -> str:
    if key_norm == "power_kw":
        return "P_kw"
    if key_norm == "fuel_kgh":
        return "Consumo_kg_h"
    if key_norm == "lhv_kj_kg":
        return "LHV_kJ_kg"
    emission_prefixes = {
        "co_pct": "CO_pct", "co2_pct": "CO2_pct", "o2_pct": "O2_pct",
        "nox_ppm": "NOx_ppm", "no_ppm": "NO_ppm", "thc_ppm": "THC_ppm",
    }
    if key_norm in emission_prefixes:
        return emission_prefixes[key_norm]
    return key_norm.upper()


def _defaults_text_value(defaults_cfg: Optional[Dict[str, str]], param: object, fallback: str = "") -> str:
    if defaults_cfg is None:
        return fallback
    if _is_blank_cell(param):
        return fallback
    p = norm_key(param)
    if not p:
        return fallback
    raw = defaults_cfg.get(p, fallback)
    return _to_str_or_empty(raw) or fallback


def _split_setting_values(raw: object) -> List[str]:
    txt = _to_str_or_empty(raw)
    if not txt:
        return []
    return [norm_key(part) for part in re.split(r"[|,;/]+", txt) if norm_key(part)]


def _filter_instrument_rows_by_defaults(
    rows: pd.DataFrame,
    defaults_cfg: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    if rows is None or rows.empty or defaults_cfg is None:
        return rows
    if "setting_param" not in rows.columns or "setting_value" not in rows.columns:
        return rows
    keep_mask = pd.Series(True, index=rows.index, dtype="bool")
    for idx, row in rows.iterrows():
        setting_param = _to_str_or_empty(row.get("setting_param", ""))
        if not setting_param:
            continue
        expected_values = _split_setting_values(row.get("setting_value", ""))
        if not expected_values or any(v in {"*", "any"} for v in expected_values):
            continue
        actual_value = norm_key(_defaults_text_value(defaults_cfg, setting_param, ""))
        if actual_value not in expected_values:
            keep_mask.loc[idx] = False
    return rows.loc[keep_mask].copy()


def _instrument_rows_for_key(
    instruments_df: pd.DataFrame,
    key_norm: str,
    defaults_cfg: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    if instruments_df is None or instruments_df.empty:
        return pd.DataFrame()
    if "key_norm" not in instruments_df.columns:
        return pd.DataFrame()
    rows = instruments_df[instruments_df["key_norm"].eq(key_norm)].copy()
    if rows.empty:
        fallback_key = {"t_e_comp_c": "t_s_agua_c", "t_s_comp_c": "t_s_agua_c"}.get(key_norm, "")
        if fallback_key:
            rows = instruments_df[instruments_df["key_norm"].eq(fallback_key)].copy()
    if rows.empty:
        return rows
    return _filter_instrument_rows_by_defaults(rows, defaults_cfg=defaults_cfg)


def _has_instrument_key(
    instruments_df: pd.DataFrame,
    key_norm: str,
    defaults_cfg: Optional[Dict[str, str]] = None,
) -> bool:
    if instruments_df is None or instruments_df.empty:
        return False
    if "key_norm" not in instruments_df.columns:
        return False
    rows = _instrument_rows_for_key(instruments_df, key_norm=key_norm, defaults_cfg=defaults_cfg)
    return not rows.empty


def _get_resolution_for_key(
    instruments_df: pd.DataFrame,
    key_norm: str,
    defaults_cfg: Optional[Dict[str, str]] = None,
) -> Optional[float]:
    if not _has_instrument_key(instruments_df, key_norm, defaults_cfg=defaults_cfg):
        return None
    rows = _instrument_rows_for_key(instruments_df, key_norm=key_norm, defaults_cfg=defaults_cfg)
    if rows.empty:
        return None
    res = pd.to_numeric(rows.get("resolution", pd.Series([], dtype="float64")), errors="coerce").abs()
    if res.dropna().empty:
        return None
    return float(res.dropna().max())


def uB_from_instruments_rev2(
    x: pd.Series,
    key_norm: str,
    instruments_df: pd.DataFrame,
    defaults_cfg: Optional[Dict[str, str]] = None,
) -> pd.Series:
    if instruments_df is None or instruments_df.empty:
        return pd.Series([pd.NA] * len(x), index=x.index)
    if not _has_instrument_key(instruments_df, key_norm, defaults_cfg=defaults_cfg):
        return pd.Series([pd.NA] * len(x), index=x.index)
    rows = _instrument_rows_for_key(instruments_df, key_norm=key_norm, defaults_cfg=defaults_cfg)
    if rows.empty:
        return pd.Series([pd.NA] * len(x), index=x.index)
    xv = pd.to_numeric(x, errors="coerce")
    u2 = pd.Series(0.0, index=xv.index, dtype="float64")
    for _, r in rows.iterrows():
        dist = str(r.get("dist", "rect")).strip().lower() or "rect"
        rmin_v = _to_float(r.get("range_min", pd.NA), default=np.nan)
        rmax_v = _to_float(r.get("range_max", pd.NA), default=np.nan)
        mask = pd.Series(True, index=xv.index)
        if np.isfinite(rmin_v):
            mask = mask & (xv >= rmin_v)
        if np.isfinite(rmax_v):
            mask = mask & (xv <= rmax_v)
        acc_abs = _to_float(r.get("acc_abs", 0.0), 0.0)
        acc_pct = _to_float(r.get("acc_pct", 0.0), 0.0)
        digits = _to_float(r.get("digits", 0.0), 0.0)
        lsd = _to_float(r.get("lsd", 0.0), 0.0)
        resolution = _to_float(r.get("resolution", 0.0), 0.0)
        limit = xv.abs() * acc_pct + acc_abs + abs(digits) * abs(lsd)
        limit = limit.where(mask, 0.0)
        if dist == "normal":
            u_acc = limit
        else:
            u_acc = rect_to_std(limit)
        u_res = res_to_std(abs(resolution))
        u_comp = (u_acc**2 + (u_res**2)) ** 0.5
        u2 = u2 + (pd.to_numeric(u_comp, errors="coerce").fillna(0.0) ** 2)
    u = (u2**0.5).where(xv.notna(), pd.NA)
    return u


def add_uncertainties_from_mappings(
    df: pd.DataFrame,
    mappings: dict,
    instruments_df: pd.DataFrame,
    N: pd.Series,
    defaults_cfg: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    out = df.copy()
    for key_norm, spec in mappings.items():
        col_mean_req = str(spec.get("mean", "")).strip()
        if not col_mean_req:
            continue
        try:
            col_mean = resolve_col(out, col_mean_req)
        except Exception as e:
            print(f"[WARN] Uncertainty: key='{key_norm}' col_mean '{col_mean_req}' nao encontrada no output. Pulando. ({e})")
            continue
        col_sd_req = str(spec.get("sd", "")).strip()
        col_sd = None
        if col_sd_req:
            try:
                col_sd = resolve_col(out, col_sd_req)
            except Exception:
                col_sd = None
        prefix = _prefix_from_key_norm(key_norm)
        if col_sd is not None and col_sd in out.columns:
            out[f"uA_{prefix}"] = pd.to_numeric(out[col_sd], errors="coerce") / (pd.to_numeric(N, errors="coerce") ** 0.5)
        else:
            out[f"uA_{prefix}"] = pd.NA
        out[f"uB_{prefix}"] = uB_from_instruments_rev2(
            pd.to_numeric(out[col_mean], errors="coerce"),
            key_norm=key_norm,
            instruments_df=instruments_df,
            defaults_cfg=defaults_cfg,
        )
        ua = pd.to_numeric(out[f"uA_{prefix}"], errors="coerce")
        ub = pd.to_numeric(out[f"uB_{prefix}"], errors="coerce")
        out[f"uc_{prefix}"] = (ua**2 + ub**2) ** 0.5
        out[f"U_{prefix}"] = K_COVERAGE * out[f"uc_{prefix}"]
    return out


def _combine_average_temperature_uncertainties(
    df: pd.DataFrame,
    *,
    mean_cols: List[str],
    source_prefixes: List[str],
    target_mean_col: str,
    target_prefix: str,
) -> pd.DataFrame:
    out = df.copy()
    existing_mean_cols = [c for c in mean_cols if c in out.columns]
    if not existing_mean_cols:
        out[target_mean_col] = pd.NA
        for suffix in ("uA", "uB", "uc", "U"):
            out[f"{suffix}_{target_prefix}"] = pd.NA
        return out
    mean_df = out[existing_mean_cols].apply(pd.to_numeric, errors="coerce")
    out[target_mean_col] = mean_df.mean(axis=1)
    n_valid = mean_df.notna().sum(axis=1).astype("float64")
    n_valid = n_valid.where(n_valid > 0, np.nan)
    for prefix_kind in ("uA", "uB"):
        cols = [f"{prefix_kind}_{p}" for p in source_prefixes if f"{prefix_kind}_{p}" in out.columns]
        if not cols:
            out[f"{prefix_kind}_{target_prefix}"] = pd.NA
            continue
        comp = out[cols].apply(pd.to_numeric, errors="coerce")
        out[f"{prefix_kind}_{target_prefix}"] = ((comp**2).sum(axis=1) ** 0.5) / n_valid
        out.loc[n_valid.isna(), f"{prefix_kind}_{target_prefix}"] = pd.NA
    ua = pd.to_numeric(out.get(f"uA_{target_prefix}", pd.NA), errors="coerce")
    ub = pd.to_numeric(out.get(f"uB_{target_prefix}", pd.NA), errors="coerce")
    out[f"uc_{target_prefix}"] = (ua**2 + ub**2) ** 0.5
    out[f"U_{target_prefix}"] = K_COVERAGE * pd.to_numeric(out[f"uc_{target_prefix}"], errors="coerce")
    return out


def _combine_delta_temperature_uncertainties(
    df: pd.DataFrame,
    *,
    minuend_col: str,
    subtrahend_col: str,
    minuend_prefix: str,
    subtrahend_prefix: str,
    target_value_col: str,
    target_prefix: str,
) -> pd.DataFrame:
    out = df.copy()
    if minuend_col not in out.columns or subtrahend_col not in out.columns:
        out[target_value_col] = pd.NA
        for suffix in ("uA", "uB", "uc", "U"):
            out[f"{suffix}_{target_prefix}"] = pd.NA
        return out
    minuend = pd.to_numeric(out[minuend_col], errors="coerce")
    subtrahend = pd.to_numeric(out[subtrahend_col], errors="coerce")
    out[target_value_col] = minuend - subtrahend
    for prefix_kind in ("uA", "uB"):
        a = pd.to_numeric(out.get(f"{prefix_kind}_{minuend_prefix}", pd.NA), errors="coerce")
        b = pd.to_numeric(out.get(f"{prefix_kind}_{subtrahend_prefix}", pd.NA), errors="coerce")
        out[f"{prefix_kind}_{target_prefix}"] = (a**2 + b**2) ** 0.5
    ua = pd.to_numeric(out.get(f"uA_{target_prefix}", pd.NA), errors="coerce")
    ub = pd.to_numeric(out.get(f"uB_{target_prefix}", pd.NA), errors="coerce")
    out[f"uc_{target_prefix}"] = (ua**2 + ub**2) ** 0.5
    out[f"U_{target_prefix}"] = K_COVERAGE * pd.to_numeric(out[f"uc_{target_prefix}"], errors="coerce")
    return out
