"""Native fuel-properties lookup.

Replaces ``legacy.load_fuel_properties_lookup`` (nanum_pipeline_29.py L4274-4317).
Reads from ``ConfigBundle.fuel_properties`` (List[Dict]) + ``ConfigBundle.defaults``
and optionally merges with a legacy ``lhv.csv`` fallback.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ..config.adapter import DEFAULT_FUEL_PROPERTY_COLUMNS

COMPOSITION_COLS = ["DIES_pct", "BIOD_pct", "EtOH_pct", "H2O_pct"]

_COLUMN_ALIASES = {
    "fuel_label": "Fuel_Label", "label": "Fuel_Label",
    "dies_pct": "DIES_pct", "dies": "DIES_pct", "diesel_pct": "DIES_pct", "diesel": "DIES_pct",
    "biod_pct": "BIOD_pct", "biod": "BIOD_pct", "biodiesel_pct": "BIOD_pct", "biodiesel": "BIOD_pct",
    "etoh_pct": "EtOH_pct", "etoh": "EtOH_pct", "e_pct": "EtOH_pct", "e": "EtOH_pct",
    "h2o_pct": "H2O_pct", "h2o": "H2O_pct", "h20_pct": "H2O_pct", "h20": "H2O_pct", "h_pct": "H2O_pct", "h": "H2O_pct",
    "lhv_kj_kg": "LHV_kJ_kg", "lhv": "LHV_kJ_kg", "pci_kj_kg": "LHV_kJ_kg", "pci": "LHV_kJ_kg",
    "fuel_density_kg_m3": "Fuel_Density_kg_m3", "density_kg_m3": "Fuel_Density_kg_m3", "density": "Fuel_Density_kg_m3",
    "fuel_cost_r_l": "Fuel_Cost_R_L", "cost_r_l": "Fuel_Cost_R_L", "cost": "Fuel_Cost_R_L",
    "reference": "reference", "source": "reference",
    "notes": "notes", "note": "notes",
}


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


def _to_str_or_empty(x: object) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    return str(x).replace("﻿", "").strip()


def _format_pct_for_label(value: object) -> str:
    numeric = _to_float(value, default=float("nan"))
    if not np.isfinite(numeric):
        return _to_str_or_empty(value)
    if abs(numeric - round(numeric)) <= 1e-9:
        return str(int(round(numeric)))
    return f"{numeric:g}"


def _fuel_label_from_components(
    dies_pct: object, biod_pct: object, etoh_pct: object, h2o_pct: object,
    tol: float = 0.6,
) -> str:
    dies = _to_float(dies_pct, default=float("nan"))
    biod = _to_float(biod_pct, default=float("nan"))
    etoh = _to_float(etoh_pct, default=float("nan"))
    h2o = _to_float(h2o_pct, default=float("nan"))

    def _near_zero(v: float) -> bool:
        return (not np.isfinite(v)) or abs(v) <= tol

    if np.isfinite(dies) and np.isfinite(biod) and abs(dies - 85.0) <= tol and abs(biod - 15.0) <= tol and _near_zero(etoh) and _near_zero(h2o):
        return "D85B15"
    if np.isfinite(etoh) and np.isfinite(h2o) and abs(etoh - 94.0) <= tol and abs(h2o - 6.0) <= tol and _near_zero(dies) and _near_zero(biod):
        return "E94H6"
    if np.isfinite(etoh) and np.isfinite(h2o) and abs(etoh - 75.0) <= tol and abs(h2o - 25.0) <= tol and _near_zero(dies) and _near_zero(biod):
        return "E75H25"
    if np.isfinite(etoh) and np.isfinite(h2o) and abs(etoh - 65.0) <= tol and abs(h2o - 35.0) <= tol and _near_zero(dies) and _near_zero(biod):
        return "E65H35"

    if np.isfinite(dies) and np.isfinite(biod) and _near_zero(etoh) and _near_zero(h2o):
        if abs(dies) <= tol:
            return f"B{_format_pct_for_label(biod)}"
        if abs(biod) <= tol:
            return f"D{_format_pct_for_label(dies)}"
        return f"D{_format_pct_for_label(dies)}B{_format_pct_for_label(biod)}"

    if np.isfinite(biod) and np.isfinite(etoh) and _near_zero(dies) and _near_zero(h2o):
        if abs(etoh) <= tol:
            return f"B{_format_pct_for_label(biod)}"
        if abs(biod) <= tol:
            return f"E{_format_pct_for_label(etoh)}"
        return f"B{_format_pct_for_label(biod)}E{_format_pct_for_label(etoh)}"

    if np.isfinite(dies) and np.isfinite(etoh) and _near_zero(biod) and _near_zero(h2o):
        if abs(etoh) <= tol:
            return f"D{_format_pct_for_label(dies)}"
        if abs(dies) <= tol:
            return f"E{_format_pct_for_label(etoh)}"
        return f"D{_format_pct_for_label(dies)}E{_format_pct_for_label(etoh)}"

    return ""


def _normalize_fuel_properties_df(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=DEFAULT_FUEL_PROPERTY_COLUMNS)

    out = df.copy()
    rename_map: Dict[str, str] = {}
    for col in out.columns:
        cl = str(col).replace("﻿", "").strip().lower()
        if cl in _COLUMN_ALIASES:
            rename_map[col] = _COLUMN_ALIASES[cl]
    out = out.rename(columns=rename_map)

    for col in DEFAULT_FUEL_PROPERTY_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA

    for col in COMPOSITION_COLS:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("Float64")
    for col in ("LHV_kJ_kg", "Fuel_Density_kg_m3", "Fuel_Cost_R_L"):
        out[col] = pd.to_numeric(out[col], errors="coerce")

    if "Fuel_Label" in out.columns:
        missing_label = out["Fuel_Label"].isna() | out["Fuel_Label"].map(
            lambda v: not _to_str_or_empty(v).strip()
        )
        if bool(missing_label.any()):
            inferred = out.apply(
                lambda row: _fuel_label_from_components(
                    row.get("DIES_pct", pd.NA), row.get("BIOD_pct", pd.NA),
                    row.get("EtOH_pct", pd.NA), row.get("H2O_pct", pd.NA),
                ),
                axis=1,
            )
            inferred = inferred.map(lambda v: v or pd.NA).astype("object")
            out.loc[missing_label, "Fuel_Label"] = inferred.loc[missing_label]

    for col in ("Fuel_Label", "reference", "notes"):
        out[col] = out[col].map(lambda v: _to_str_or_empty(v) or pd.NA)

    return out[DEFAULT_FUEL_PROPERTY_COLUMNS].copy()


def _fill_fuel_property_defaults(
    fuel_df: pd.DataFrame, defaults: Dict[str, str],
) -> pd.DataFrame:
    if fuel_df is None or fuel_df.empty:
        return pd.DataFrame(columns=DEFAULT_FUEL_PROPERTY_COLUMNS)

    out = _normalize_fuel_properties_df(fuel_df)
    if out.empty:
        return out

    for idx, row in out.iterrows():
        label = _to_str_or_empty(row.get("Fuel_Label", "")).strip()
        if not label:
            continue
        density = _to_float(row.get("Fuel_Density_kg_m3", pd.NA), default=float("nan"))
        cost = _to_float(row.get("Fuel_Cost_R_L", pd.NA), default=float("nan"))
        if not np.isfinite(density) or density <= 0:
            key = f"fuel_density_kg_m3_{label}".lower()
            d_default = _to_float(defaults.get(key, ""), default=float("nan"))
            if np.isfinite(d_default) and d_default > 0:
                out.at[idx, "Fuel_Density_kg_m3"] = float(d_default)
        if not np.isfinite(cost) or cost <= 0:
            key = f"fuel_cost_r_l_{label}".lower()
            c_default = _to_float(defaults.get(key, ""), default=float("nan"))
            if np.isfinite(c_default) and c_default > 0:
                out.at[idx, "Fuel_Cost_R_L"] = float(c_default)
    return out


def _load_lhv_csv(lhv_csv_path: Path, defaults: Dict[str, str]) -> pd.DataFrame:
    if not lhv_csv_path.exists():
        return pd.DataFrame(columns=DEFAULT_FUEL_PROPERTY_COLUMNS)
    df = pd.read_csv(lhv_csv_path, sep=None, engine="python", encoding="utf-8-sig")
    df = _normalize_fuel_properties_df(df)
    if "LHV_kJ_kg" not in df.columns:
        return pd.DataFrame(columns=DEFAULT_FUEL_PROPERTY_COLUMNS)
    return _fill_fuel_property_defaults(df, defaults)


def load_fuel_properties(
    fuel_rows: List[Dict[str, Any]],
    defaults: Dict[str, str],
    lhv_csv_path: Optional[Path] = None,
) -> pd.DataFrame:
    configured = pd.DataFrame(columns=DEFAULT_FUEL_PROPERTY_COLUMNS)
    if fuel_rows:
        configured = _fill_fuel_property_defaults(pd.DataFrame(fuel_rows), defaults)
        if not configured.empty:
            lhv = pd.to_numeric(configured.get("LHV_kJ_kg", pd.Series(dtype="float64")), errors="coerce")
            if lhv.notna().any():
                return configured

    legacy = pd.DataFrame(columns=DEFAULT_FUEL_PROPERTY_COLUMNS)
    if lhv_csv_path is not None:
        try:
            legacy = _load_lhv_csv(lhv_csv_path, defaults)
        except Exception:
            pass

    if configured.empty:
        return legacy
    if legacy.empty:
        return configured

    configured_keys = {
        (
            _to_float(row.get("DIES_pct", pd.NA), default=float("nan")),
            _to_float(row.get("BIOD_pct", pd.NA), default=float("nan")),
            _to_float(row.get("EtOH_pct", pd.NA), default=float("nan")),
            _to_float(row.get("H2O_pct", pd.NA), default=float("nan")),
        )
        for _, row in configured.iterrows()
    }
    missing: List[Dict[str, Any]] = []
    for _, row in legacy.iterrows():
        key = (
            _to_float(row.get("DIES_pct", pd.NA), default=float("nan")),
            _to_float(row.get("BIOD_pct", pd.NA), default=float("nan")),
            _to_float(row.get("EtOH_pct", pd.NA), default=float("nan")),
            _to_float(row.get("H2O_pct", pd.NA), default=float("nan")),
        )
        if key not in configured_keys:
            missing.append(row.to_dict())
    if not missing:
        return configured
    combined = pd.concat([configured, pd.DataFrame(missing)], ignore_index=True)
    return _normalize_fuel_properties_df(combined)
