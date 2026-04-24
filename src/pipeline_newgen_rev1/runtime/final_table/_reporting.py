"""Reporting rounding: applies resolution-based rounding per the reporting config."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ._helpers import _to_float, norm_key, resolve_col


def _round_half_up_to_resolution(x: pd.Series, res: float) -> pd.Series:
    s = pd.to_numeric(x, errors="coerce")
    if res <= 0:
        return s
    q = s / res
    pos = q.where(q >= 0)
    neg = q.where(q < 0)
    pos_r = np.floor(pos + 0.5)
    neg_r = np.ceil(neg - 0.5)
    out = q.copy()
    out = out.where(q.isna(), np.nan)
    out = out.where(q < 0, pos_r)
    out = out.where(q >= 0, neg_r)
    return out * res


def _apply_reporting_rounding(df: pd.DataFrame, mappings: dict, reporting_df: pd.DataFrame) -> pd.DataFrame:
    if reporting_df is None or reporting_df.empty:
        return df
    out = df.copy()
    for _, r in reporting_df.iterrows():
        key_norm = norm_key(r.get("key", ""))
        if not key_norm:
            continue
        if key_norm not in mappings:
            continue
        col_mean = str(mappings[key_norm].get("mean", "")).strip()
        if not col_mean:
            continue
        if col_mean not in out.columns:
            try:
                col_mean = resolve_col(out, col_mean)
            except Exception:
                continue
        res = _to_float(r.get("report_resolution", 0.0), 0.0)
        if res <= 0:
            continue
        rule = str(r.get("rule", "round_half_up")).strip().lower()
        new_col = f"{col_mean}_report"
        if new_col in out.columns:
            continue
        if rule == "round_half_up":
            out[new_col] = _round_half_up_to_resolution(out[col_mean], res)
        else:
            v = pd.to_numeric(out[col_mean], errors="coerce")
            out[new_col] = (np.round(v / res) * res)
    return out
