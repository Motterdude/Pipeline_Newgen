"""Sweep value binning: cluster close measurements into stable bins.

Port of legacy nanum_pipeline_30.py L4454-4572.
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd

from ..ui.runtime_preflight.constants import (
    SWEEP_BIN_LABEL_COL,
    SWEEP_BIN_VALUE_COL,
    SWEEP_VALUE_COL,
)


def format_sweep_bin_label(value: object) -> str:
    try:
        val = float(value)
    except Exception:
        return str(value or "").strip()
    if not np.isfinite(val):
        return ""
    text = f"{val:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def _sorted_unique_finite_values(values: pd.Series) -> List[float]:
    numeric = pd.to_numeric(values, errors="coerce")
    out: List[float] = []
    for raw in numeric.dropna().tolist():
        val = round(float(raw), 6)
        if np.isfinite(val) and val not in out:
            out.append(val)
    return sorted(out)


def cluster_sweep_bin_centers(values: pd.Series, tol: float) -> List[float]:
    unique_values = _sorted_unique_finite_values(values)
    if not unique_values:
        return []
    if tol <= 0:
        return unique_values

    clusters: List[List[float]] = [[unique_values[0]]]
    for value in unique_values[1:]:
        current = clusters[-1]
        current_mean = float(np.mean(current))
        if abs(value - current_mean) <= tol:
            current.append(value)
            continue
        clusters.append([value])
    return [round(float(np.mean(cluster)), 6) for cluster in clusters if cluster]


def _assign_value_to_sweep_bin(
    value: object, *, centers: List[float], tol: float
) -> float:
    try:
        raw = float(value)
    except Exception:
        return float("nan")
    if not np.isfinite(raw):
        return float("nan")
    if not centers:
        return round(float(raw), 6)

    candidates: List[Tuple[float, float]] = []
    for idx, center in enumerate(centers):
        lower = center - tol
        upper = center + tol
        if idx > 0:
            lower = max(lower, (centers[idx - 1] + center) / 2.0)
        if idx + 1 < len(centers):
            upper = min(upper, (center + centers[idx + 1]) / 2.0)
        if lower <= raw <= upper:
            candidates.append((abs(raw - center), center))

    if candidates:
        return min(candidates, key=lambda item: (item[0], item[1]))[1]

    nearest = min(centers, key=lambda c: abs(raw - c))
    if abs(raw - nearest) <= tol:
        return nearest
    return round(float(raw), 6)


def _candidate_sweep_bin_centers(
    df: pd.DataFrame, *, x_col: str, tol: float
) -> List[float]:
    if df is None or df.empty:
        return []
    if SWEEP_VALUE_COL in df.columns:
        centers = _sorted_unique_finite_values(df[SWEEP_VALUE_COL])
        if centers:
            return centers
    if x_col in df.columns:
        return cluster_sweep_bin_centers(df[x_col], tol)
    return []


def apply_sweep_binning(
    df: pd.DataFrame,
    *,
    x_col: str,
    tol: float,
    sweep_active: bool,
) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    if out.empty:
        out[SWEEP_BIN_VALUE_COL] = pd.Series(dtype="float64")
        out[SWEEP_BIN_LABEL_COL] = pd.Series(dtype="object")
        return out

    if not sweep_active:
        if x_col in out.columns:
            numeric = pd.to_numeric(out[x_col], errors="coerce")
            out[SWEEP_BIN_VALUE_COL] = numeric
            out[SWEEP_BIN_LABEL_COL] = numeric.map(format_sweep_bin_label).replace("", pd.NA)
        return out

    if x_col not in out.columns:
        out[SWEEP_BIN_VALUE_COL] = pd.Series(np.nan, index=out.index, dtype="float64")
        out[SWEEP_BIN_LABEL_COL] = pd.Series(pd.NA, index=out.index, dtype="object")
        return out

    centers = _candidate_sweep_bin_centers(out, x_col=x_col, tol=tol)
    raw_series = pd.to_numeric(out[x_col], errors="coerce")
    binned = raw_series.map(
        lambda value: _assign_value_to_sweep_bin(value, centers=centers, tol=tol)
    )
    out[SWEEP_BIN_VALUE_COL] = pd.to_numeric(binned, errors="coerce")
    out[SWEEP_BIN_LABEL_COL] = (
        out[SWEEP_BIN_VALUE_COL].map(format_sweep_bin_label).replace("", pd.NA)
    )

    changed_count = int(
        (
            raw_series.round(6)
            .sub(pd.to_numeric(out[SWEEP_BIN_VALUE_COL], errors="coerce").round(6))
            .abs()
            > 1e-9
        )
        .fillna(False)
        .sum()
    )
    if changed_count > 0:
        print(
            f"[INFO] Sweep binning: {changed_count} ponto(s) ajustado(s) para bins "
            f"com tolerancia +/-{tol:.4f} usando {len(centers)} centro(s)."
        )
    else:
        print(
            f"[INFO] Sweep binning: nenhum ajuste necessario; "
            f"tolerancia +/-{tol:.4f}, centros={len(centers)}."
        )
    return out
