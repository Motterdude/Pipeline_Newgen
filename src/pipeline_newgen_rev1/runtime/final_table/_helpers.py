"""Shared utility functions used by multiple final-table modules."""
from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


def norm_key(x: object) -> str:
    return str(x).replace("﻿", "").strip().lower()


def _canon_name(x: object) -> str:
    s = str(x).replace("﻿", "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s)


def _normalize_repeated_stat_tokens_in_name(x: object) -> str:
    s = str(x).replace("﻿", "").strip()
    if not s:
        return s
    replacements = [
        ("_mean_mean_of_windows", "_mean_of_windows"),
        ("_mean_sd_of_windows", "_sd_of_windows"),
        ("_sd_mean_of_windows", "_sd_of_windows"),
        ("_sd_sd_of_windows", "_sd_of_windows"),
        ("_mean_mean", "_mean"),
        ("_sd_sd", "_sd"),
    ]
    prev = None
    while prev != s:
        prev = s
        for old, new in replacements:
            s = s.replace(old, new)
    s = re.sub(r"__+", "_", s)
    return s


def _is_blank_cell(x: object) -> bool:
    if x is None:
        return True
    try:
        if pd.isna(x):
            return True
    except Exception:
        pass
    s = str(x).replace("﻿", "").strip()
    return s == "" or s.lower() == "nan"


def _to_str_or_empty(x: object) -> str:
    return "" if _is_blank_cell(x) else str(x).replace("﻿", "").strip()


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
    if s == "":
        return default
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return default


def _nan_series(index: pd.Index) -> pd.Series:
    return pd.Series(np.nan, index=index, dtype="float64")


def resolve_col(df: pd.DataFrame, requested: str) -> str:
    requested = str(requested).replace("﻿", "").strip()
    if not requested:
        raise KeyError("Nome de coluna solicitado esta vazio (verifique Mappings no config).")
    if requested in df.columns:
        return requested
    low_map = {str(c).lower().strip(): c for c in df.columns}
    req_low = requested.lower().strip()
    if req_low in low_map:
        return low_map[req_low]
    canon_map = {_canon_name(c): c for c in df.columns}
    req_canon = _canon_name(requested)
    if req_canon in canon_map:
        return canon_map[req_canon]
    req_stats_norm = _normalize_repeated_stat_tokens_in_name(requested)
    if req_stats_norm in df.columns:
        return req_stats_norm
    stats_norm_map: Dict[str, str] = {}
    for c in df.columns:
        c_norm = _normalize_repeated_stat_tokens_in_name(c)
        if c_norm not in stats_norm_map:
            stats_norm_map[c_norm] = c
    if req_stats_norm in stats_norm_map:
        return stats_norm_map[req_stats_norm]
    stats_norm_canon_map: Dict[str, str] = {}
    for c in df.columns:
        c_norm = _normalize_repeated_stat_tokens_in_name(c)
        c_norm_canon = _canon_name(c_norm)
        if c_norm_canon not in stats_norm_canon_map:
            stats_norm_canon_map[c_norm_canon] = c
    req_stats_canon = _canon_name(req_stats_norm)
    if req_stats_canon in stats_norm_canon_map:
        return stats_norm_canon_map[req_stats_canon]
    suggestion = difflib.get_close_matches(requested, list(df.columns), n=6)
    sug_txt = f" Sugestoes: {suggestion}" if suggestion else ""
    raise KeyError(f"Coluna '{requested}' nao encontrada no dataframe.{sug_txt}")


def _find_first_col_by_substrings(df: pd.DataFrame, substrings: List[str]) -> Optional[str]:
    for c in df.columns:
        cl = str(c).lower()
        if all(str(s).lower() in cl for s in substrings):
            return c
    return None


def _find_preferred_column(
    df: pd.DataFrame,
    *,
    preferred_names: List[str],
    include_tokens: List[str],
    exclude_tokens: Optional[List[str]] = None,
) -> Optional[str]:
    for requested in preferred_names:
        req = _to_str_or_empty(requested)
        if not req:
            continue
        try:
            return resolve_col(df, req)
        except Exception:
            continue
    exclude_tokens = exclude_tokens or []
    for column in df.columns:
        canon = _canon_name(column)
        if any(_canon_name(token) not in canon for token in include_tokens):
            continue
        if any(_canon_name(token) in canon for token in exclude_tokens):
            continue
        return column
    return None


def _resolve_existing_column(df: pd.DataFrame, preferred_name: str, fallback_tokens: List[str]) -> Optional[str]:
    preferred = str(preferred_name or "").strip()
    if preferred and preferred in df.columns:
        return preferred
    return _find_first_col_by_substrings(df, fallback_tokens)
