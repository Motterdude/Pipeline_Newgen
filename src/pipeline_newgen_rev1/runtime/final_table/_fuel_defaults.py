"""Fuel blend labels, density/cost defaults, and LHV lookup."""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from ..fuel_properties import _fuel_label_from_components
from ._helpers import _to_float, norm_key


def _fuel_blend_labels(df: pd.DataFrame, tol: float = 0.6) -> pd.Series:
    idx = df.index
    comps = pd.DataFrame(
        {
            "DIES_pct": pd.to_numeric(df.get("DIES_pct", pd.Series(pd.NA, index=idx)), errors="coerce"),
            "BIOD_pct": pd.to_numeric(df.get("BIOD_pct", pd.Series(pd.NA, index=idx)), errors="coerce"),
            "EtOH_pct": pd.to_numeric(df.get("EtOH_pct", pd.Series(pd.NA, index=idx)), errors="coerce"),
            "H2O_pct": pd.to_numeric(df.get("H2O_pct", pd.Series(pd.NA, index=idx)), errors="coerce"),
        },
        index=idx,
    )
    labels = comps.apply(
        lambda row: _fuel_label_from_components(
            row["DIES_pct"], row["BIOD_pct"], row["EtOH_pct"], row["H2O_pct"], tol=tol,
        ),
        axis=1,
    )
    return labels.map(lambda value: value or pd.NA).astype("object")


def _fuel_default_lookup_series(
    df: pd.DataFrame,
    defaults_cfg: Dict[str, str],
    *,
    field: str,
) -> Tuple[pd.Series, List[str]]:
    labels = _fuel_blend_labels(df)
    values = pd.Series(np.nan, index=df.index, dtype="float64")
    missing: List[str] = []
    field_prefix = {
        "density_param": "FUEL_DENSITY_KG_M3_",
        "cost_param": "FUEL_COST_R_L_",
    }.get(field, "")
    if not field_prefix:
        raise KeyError(f"Campo de lookup de combustivel nao suportado: {field}")
    unique_labels = sorted({str(label).strip() for label in labels.dropna().tolist() if str(label).strip()})
    for label in unique_labels:
        mask = labels.eq(label)
        if not bool(mask.any()):
            continue
        param_name = f"{field_prefix}{label}"
        param_value = _to_float(defaults_cfg.get(norm_key(param_name), ""), default=float("nan"))
        if np.isfinite(param_value) and (param_value > 0):
            values.loc[mask] = float(param_value)
        else:
            missing.append(f"{label} -> {param_name}")
    return values, missing


def _lookup_lhv_for_blend(
    lhv_df: pd.DataFrame,
    *,
    etoh_pct: float,
    h2o_pct: float,
    tol: float = 0.6,
) -> float:
    if lhv_df is None or lhv_df.empty:
        return float("nan")
    if "LHV_kJ_kg" not in lhv_df.columns:
        return float("nan")
    etoh = pd.to_numeric(lhv_df.get("EtOH_pct", pd.Series(pd.NA, index=lhv_df.index)), errors="coerce")
    h2o = pd.to_numeric(lhv_df.get("H2O_pct", pd.Series(pd.NA, index=lhv_df.index)), errors="coerce")
    m = (etoh.sub(etoh_pct).abs() <= tol) & (h2o.sub(h2o_pct).abs() <= tol)
    if not bool(m.any()):
        return float("nan")
    vals = pd.to_numeric(lhv_df.loc[m, "LHV_kJ_kg"], errors="coerce").dropna()
    if vals.empty:
        return float("nan")
    return float(vals.iloc[0])
