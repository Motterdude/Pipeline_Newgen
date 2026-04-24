from __future__ import annotations

import re
from math import sqrt
from typing import Any, Dict, List, Optional

import pandas as pd

from .constants import B_ETANOL_COL_CANDIDATES


SQRT_12 = sqrt(12.0)

_SUFFIX_REPLACEMENTS = [
    ("_mean_mean_of_windows", "_mean_of_windows"),
    ("_mean_sd_of_windows", "_sd_of_windows"),
    ("_sd_mean_of_windows", "_sd_of_windows"),
    ("_sd_sd_of_windows", "_sd_of_windows"),
    ("_mean_mean", "_mean"),
    ("_sd_sd", "_sd"),
]


def find_b_etanol_col(df: pd.DataFrame) -> str:
    for c in B_ETANOL_COL_CANDIDATES:
        if c in df.columns:
            return c
    raise KeyError(
        f"Column not found among candidates {B_ETANOL_COL_CANDIDATES}. "
        f"Available (first 40): {list(df.columns)[:40]}"
    )


def res_to_std(step: float) -> float:
    return step / SQRT_12 if step > 0 else 0.0


def normalize_repeated_stat_tokens(name: str) -> str:
    s = str(name).replace("﻿", "").strip()
    if not s:
        return s
    prev = None
    while prev != s:
        prev = s
        for old, new in _SUFFIX_REPLACEMENTS:
            s = s.replace(old, new)
    s = re.sub(r"__+", "_", s)
    return s


def _rows_for_key(instruments: List[Dict[str, Any]], key_norm: str) -> List[Dict[str, Any]]:
    if not instruments:
        return []
    key = key_norm.strip().lower()
    result: List[Dict[str, Any]] = []
    for row in instruments:
        row_key = str(row.get("key", "")).strip().lower()
        if row_key == key:
            result.append(row)
    return result


def _to_float(x: object, default: float = 0.0) -> float:
    if x is None:
        return default
    try:
        if pd.isna(x):
            return default
    except Exception:
        pass
    if isinstance(x, (int, float)):
        try:
            return float(x)
        except Exception:
            return default
    s = str(x).replace("﻿", "").strip()
    if s == "" or s.lower() == "nan":
        return default
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return default


def has_instrument_key(instruments: List[Dict[str, Any]], key_norm: str) -> bool:
    return len(_rows_for_key(instruments, key_norm)) > 0


def get_resolution_for_key(instruments: List[Dict[str, Any]], key_norm: str) -> Optional[float]:
    rows = _rows_for_key(instruments, key_norm)
    if not rows:
        return None
    best: Optional[float] = None
    for row in rows:
        val = _to_float(row.get("resolution"), default=float("nan"))
        if pd.notna(val) and val != 0.0:
            absval = abs(val)
            if best is None or absval > best:
                best = absval
    return best
