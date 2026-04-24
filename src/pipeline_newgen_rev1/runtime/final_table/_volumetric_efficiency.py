"""Volumetric efficiency (ETA_V) from airflow method."""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from ._helpers import _resolve_existing_column, _to_float, _to_str_or_empty, norm_key
from .constants import R_AIR_DRY_J_KG_K


def add_volumetric_efficiency_from_airflow_method_inplace(df: pd.DataFrame, defaults_cfg: Dict[str, str]) -> pd.DataFrame:
    out = df.copy()

    displacement_l = _to_float(defaults_cfg.get(norm_key("ENGINE_DISPLACEMENT_L"), ""), default=3.992)
    ref_pressure_kpa = _to_float(defaults_cfg.get(norm_key("VOL_EFF_REF_PRESSURE_kPa"), ""), default=101.3)
    rpm_col_name = _to_str_or_empty(defaults_cfg.get(norm_key("VOL_EFF_RPM_COL"), "")) or "Rotação_mean_of_windows"

    for column in (
        "VOL_EFF_AIR_kg_h_USED", "VOL_EFF_THEORETICAL_AIR_kg_h",
        "VOL_EFF_RHO_REF_kg_m3", "VOL_EFF_RPM_USED", "ETA_V", "ETA_V_pct",
    ):
        if column not in out.columns:
            out[column] = pd.NA
    out["VOL_EFF_AIR_SOURCE"] = pd.Series(pd.NA, index=out.index, dtype="object")
    out["VOL_EFF_REF_PRESSURE_kPa"] = ref_pressure_kpa if np.isfinite(ref_pressure_kpa) else pd.NA

    if not np.isfinite(displacement_l) or displacement_l <= 0:
        print("[WARN] ENGINE_DISPLACEMENT_L invalida; nao calculei eficiencia volumetrica.")
        return out
    if not np.isfinite(ref_pressure_kpa) or ref_pressure_kpa <= 0:
        print("[WARN] VOL_EFF_REF_PRESSURE_kPa invalida; nao calculei eficiencia volumetrica.")
        return out

    t_col = _resolve_existing_column(out, "T_ADMISSAO_mean_of_windows", ["t", "admiss"])
    rpm_col = _resolve_existing_column(out, rpm_col_name, ["rotação", "rotacao", "rpm motor", "rpm"])
    if t_col is None or rpm_col is None:
        print(f"[WARN] Nao calculei eficiencia volumetrica: t_col={t_col}, rpm_col={rpm_col}.")
        return out

    displacement_m3 = displacement_l / 1000.0
    intake_t_k = pd.to_numeric(out[t_col], errors="coerce") + 273.15
    rpm = pd.to_numeric(out[rpm_col], errors="coerce")
    rho_ref = (ref_pressure_kpa * 1000.0) / (R_AIR_DRY_J_KG_K * intake_t_k)
    theoretical_air_kg_h = rho_ref * displacement_m3 * (rpm / 2.0) * 60.0

    out["VOL_EFF_RHO_REF_kg_m3"] = rho_ref
    out["VOL_EFF_THEORETICAL_AIR_kg_h"] = theoretical_air_kg_h
    out["VOL_EFF_RPM_USED"] = rpm

    air_used = pd.to_numeric(out.get("Air_kg_h", pd.NA), errors="coerce")
    airflow_method = out.get("Airflow_Method", pd.Series(pd.NA, index=out.index, dtype="object"))
    valid_air_mask = air_used.gt(0)
    out.loc[valid_air_mask, "VOL_EFF_AIR_SOURCE"] = airflow_method.loc[valid_air_mask]
    out.loc[valid_air_mask & out["VOL_EFF_AIR_SOURCE"].isna(), "VOL_EFF_AIR_SOURCE"] = "Air_kg_h"

    valid = air_used.gt(0) & theoretical_air_kg_h.gt(0) & intake_t_k.gt(0) & rpm.gt(0)
    eta_v = (air_used / theoretical_air_kg_h).where(valid, pd.NA)

    out["VOL_EFF_AIR_kg_h_USED"] = air_used
    out["ETA_V"] = eta_v
    out["ETA_V_pct"] = eta_v * 100.0
    return out
