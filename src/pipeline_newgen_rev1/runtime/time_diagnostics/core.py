"""Port nativo de build_time_diagnostics.

Reproduz fielmente o comportamento de nanum_pipeline_29.py::build_time_diagnostics
(linhas 2097-2219), portando também os helpers privados necessários:
_parse_time_series, _find_first_col_by_substrings, _canon_name, _basename_parts,
_basename_source_folder_parts, _basename_source_folder_display,
_basename_source_file, _infer_sentido_carga_from_folder_parts,
_infer_iteracao_from_folder_parts, e versões enxutas de
add_source_identity_columns / add_run_context_columns.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .constants import (
    DEFAULT_MAX_ACT_CONTROL_ERROR_C,
    DEFAULT_MAX_DELTA_BETWEEN_SAMPLES_MS,
    DEFAULT_MAX_ECT_CONTROL_ERROR_C,
)


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


def _canon_name(x: object) -> str:
    s = str(x).replace("﻿", "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s)


def _basename_parts(basename: object) -> List[str]:
    return [str(p).strip() for p in str(basename).split("__") if str(p).strip()]


def _basename_source_folder_parts(basename: object) -> List[str]:
    parts = _basename_parts(basename)
    if len(parts) <= 1:
        return []
    return parts[:-1]


def _basename_source_folder_display(basename: object) -> str:
    return " / ".join(_basename_source_folder_parts(basename))


def _basename_source_file(basename: object) -> str:
    parts = _basename_parts(basename)
    if not parts:
        return ""
    return parts[-1]


def _infer_sentido_carga_from_folder_parts(parts: List[str]) -> object:
    for part in reversed(parts):
        s = _canon_name(part).replace("_", " ").replace("-", " ")
        if "subindo" in s or "subida" in s or re.search(r"\bup\b", s):
            return "subida"
        if "descendo" in s or "descida" in s or re.search(r"\bdown\b", s):
            return "descida"
    return pd.NA


def _infer_iteracao_from_folder_parts(parts: List[str]) -> object:
    for part in reversed(parts):
        m = re.search(r"(\d+)\s*$", str(part))
        if m:
            return int(m.group(1))
    for part in reversed(parts):
        nums = re.findall(r"\d+", str(part))
        if nums:
            return int(nums[-1])
    return pd.NA


def _find_first_col_by_substrings(df: pd.DataFrame, substrings: List[str]) -> Optional[str]:
    cols = list(df.columns)
    for c in cols:
        cl = str(c).lower()
        ok = True
        for s in substrings:
            if str(s).lower() not in cl:
                ok = False
                break
        if ok:
            return c
    return None


def _resolve_time_col(df: pd.DataFrame, requested: str) -> Optional[str]:
    if requested in df.columns:
        return requested
    lowered = {str(c).lower(): c for c in df.columns}
    return lowered.get(str(requested).lower())


def _parse_time_series(s: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(s):
        return pd.to_datetime(s, errors="coerce")
    dt = pd.to_datetime(s, errors="coerce")
    if dt.notna().any():
        return dt
    v = pd.to_numeric(s, errors="coerce")
    if v.notna().sum() == 0:
        return pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    # Fallback for Excel serial date/time values.
    return pd.to_datetime(v, unit="D", origin="1899-12-30", errors="coerce")


def _add_source_identity(df: pd.DataFrame) -> pd.DataFrame:
    """Minimal port of legacy `add_source_identity_columns` — adds SourceFolder/SourceFile from BaseName."""
    if df is None or df.empty or "BaseName" not in df.columns:
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    out = df.copy()
    out["SourceFolder"] = out["BaseName"].map(_basename_source_folder_display)
    out["SourceFile"] = out["BaseName"].map(_basename_source_file)
    return out


def _add_run_context(df: pd.DataFrame) -> pd.DataFrame:
    """Minimal port of legacy `add_run_context_columns` — adds Sentido_Carga and Iteracao from BaseName folder parts."""
    if df is None or df.empty or "BaseName" not in df.columns:
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    out = df.copy()
    folder_parts = out["BaseName"].map(_basename_source_folder_parts)
    out["Sentido_Carga"] = folder_parts.map(_infer_sentido_carga_from_folder_parts)
    out["Iteracao"] = pd.to_numeric(
        folder_parts.map(_infer_iteracao_from_folder_parts), errors="coerce"
    ).astype("Int64")
    return out


def build_time_diagnostics(
    lv_raw: pd.DataFrame,
    time_col: str = "Time",
    quality_cfg: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    """Port nativo direto de nanum_pipeline_29.py::build_time_diagnostics (linhas 2097-2219)."""
    quality_cfg = quality_cfg or {}
    max_delta_ms = _to_float(
        quality_cfg.get("MAX_DELTA_BETWEEN_SAMPLES_ms", DEFAULT_MAX_DELTA_BETWEEN_SAMPLES_MS),
        DEFAULT_MAX_DELTA_BETWEEN_SAMPLES_MS,
    )
    max_delta_s = max_delta_ms / 1000.0
    max_act_error_c = _to_float(
        quality_cfg.get("MAX_ACT_CONTROL_ERROR", DEFAULT_MAX_ACT_CONTROL_ERROR_C),
        DEFAULT_MAX_ACT_CONTROL_ERROR_C,
    )
    max_ect_error_c = _to_float(
        quality_cfg.get("MAX_ECT_CONTROL_ERROR", DEFAULT_MAX_ECT_CONTROL_ERROR_C),
        DEFAULT_MAX_ECT_CONTROL_ERROR_C,
    )

    resolved = _resolve_time_col(lv_raw, time_col)
    if resolved is None:
        resolved = _resolve_time_col(lv_raw, "TIME")
    if resolved is None or resolved not in lv_raw.columns:
        return pd.DataFrame()
    time_col = resolved

    base_cols = [
        c
        for c in ["BaseName", "Load_kW", "DIES_pct", "BIOD_pct", "EtOH_pct", "H2O_pct", "Index"]
        if c in lv_raw.columns
    ]
    out = lv_raw[base_cols + [time_col]].copy()
    out = _add_source_identity(out)
    out = _add_run_context(out)

    t = _parse_time_series(out[time_col])
    base_name_series = out.get("BaseName", pd.Series([pd.NA] * len(out), index=out.index))
    out["TIME_PARSED"] = t
    out["TIME_HOUR"] = t.dt.hour.astype("Int64")
    out["TIME_MINUTE"] = t.dt.minute.astype("Int64")
    out["TIME_SECOND"] = t.dt.second.astype("Int64")
    out["TIME_MILLISECOND"] = (t.dt.microsecond // 1000).astype("Int64")

    prev_t = t.groupby(base_name_series, dropna=False, sort=False).shift(1)
    next_t = t.groupby(base_name_series, dropna=False, sort=False).shift(-1)

    delta_from_prev_s = (t - prev_t).dt.total_seconds()
    delta_to_next_s = (next_t - t).dt.total_seconds()
    out["TIME_DELTA_FROM_PREV_s"] = delta_from_prev_s
    out["TIME_DELTA_TO_NEXT_s"] = delta_to_next_s
    out["TIME_DELTA_TO_NEXT_ms"] = delta_to_next_s * 1000.0

    typical_dt = delta_to_next_s.groupby(base_name_series, dropna=False, sort=False).transform("median")
    out["TIME_DELTA_REFERENCE_s"] = typical_dt
    out["TIME_DELTA_ERROR_ms"] = (delta_to_next_s - typical_dt) * 1000.0
    out["MAX_DELTA_BETWEEN_SAMPLES_ms"] = max_delta_ms
    out["TIME_DELTA_LIMIT_s"] = max_delta_s
    out["TIME_DELTA_LIMIT_ms"] = max_delta_ms
    out["TIME_DELTA_ERROR_FLAG"] = delta_to_next_s > max_delta_s
    out["TIME_SAMPLE_GLOBAL"] = np.arange(len(out), dtype=int)

    t_adm_col = (
        "T_ADMISSAO"
        if "T_ADMISSAO" in lv_raw.columns
        else _find_first_col_by_substrings(lv_raw, ["t", "admiss"])
    )
    dem_act_col = (
        "DEM ACT AQUECEDOR"
        if "DEM ACT AQUECEDOR" in lv_raw.columns
        else _find_first_col_by_substrings(lv_raw, ["dem", "act"])
    )
    out["MAX_ACT_CONTROL_ERROR"] = max_act_error_c
    out["ACT_CTRL_ACTUAL_C"] = pd.NA
    out["ACT_CTRL_TARGET_C"] = pd.NA
    out["ACT_CTRL_ERROR_C"] = pd.NA
    out["ACT_CTRL_ERROR_ABS_C"] = pd.NA
    out["ACT_CTRL_ERROR_FLAG"] = pd.NA
    if t_adm_col and dem_act_col:
        act_actual = pd.to_numeric(lv_raw[t_adm_col], errors="coerce")
        act_target = pd.to_numeric(lv_raw[dem_act_col], errors="coerce")
        act_err = act_actual - act_target
        out["ACT_CTRL_ACTUAL_C"] = act_actual
        out["ACT_CTRL_TARGET_C"] = act_target
        out["ACT_CTRL_ERROR_C"] = act_err
        out["ACT_CTRL_ERROR_ABS_C"] = act_err.abs()
        out["ACT_CTRL_ERROR_FLAG"] = act_err.abs() > max_act_error_c

    t_s_agua_col = None
    for cand in ["T_S_AGUA", "T_S_ÁGUA", "T_S AGUA", "T_S ÁGUA"]:
        if cand in lv_raw.columns:
            t_s_agua_col = cand
            break
    if t_s_agua_col is None:
        t_s_agua_col = _find_first_col_by_substrings(lv_raw, ["t_s", "agua"])
    if t_s_agua_col is None:
        t_s_agua_col = _find_first_col_by_substrings(lv_raw, ["t_s", "água"])

    dem_th2o_col = None
    for cand in ["DEM_TH2O", "DEM TH2O"]:
        if cand in lv_raw.columns:
            dem_th2o_col = cand
            break
    if dem_th2o_col is None:
        dem_th2o_col = _find_first_col_by_substrings(lv_raw, ["dem", "th2o"])

    out["MAX_ECT_CONTROL_ERROR"] = max_ect_error_c
    out["ECT_CTRL_ACTUAL_C"] = pd.NA
    out["ECT_CTRL_TARGET_C"] = pd.NA
    out["ECT_CTRL_LIMIT_LOW_C"] = pd.NA
    out["ECT_CTRL_LIMIT_HIGH_C"] = pd.NA
    out["ECT_CTRL_ERROR_C"] = pd.NA
    out["ECT_CTRL_ERROR_ABS_C"] = pd.NA
    out["ECT_CTRL_ERROR_FLAG"] = pd.NA
    if t_s_agua_col and dem_th2o_col:
        ect_actual = pd.to_numeric(lv_raw[t_s_agua_col], errors="coerce")
        ect_target = pd.to_numeric(lv_raw[dem_th2o_col], errors="coerce")
        ect_err = ect_actual - ect_target
        out["ECT_CTRL_ACTUAL_C"] = ect_actual
        out["ECT_CTRL_TARGET_C"] = ect_target
        out["ECT_CTRL_LIMIT_LOW_C"] = ect_target - max_ect_error_c
        out["ECT_CTRL_LIMIT_HIGH_C"] = ect_target + max_ect_error_c
        out["ECT_CTRL_ERROR_C"] = ect_err
        out["ECT_CTRL_ERROR_ABS_C"] = ect_err.abs()
        out["ECT_CTRL_ERROR_FLAG"] = ect_err.abs() > max_ect_error_c

    return out
