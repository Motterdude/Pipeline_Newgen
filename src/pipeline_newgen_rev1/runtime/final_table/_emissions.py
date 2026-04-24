"""Specific emissions g/kWh with H2O mass balance."""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from ._helpers import _resolve_existing_column, _to_float, norm_key
from ._psychrometrics import _humidity_ratio_w_from_rh
from .constants import (
    H_MASS_FRAC_BIODIESEL,
    H_MASS_FRAC_DIESEL,
    H_MASS_FRAC_ETHANOL,
    MW_C3H8_KG_KMOL,
    MW_CO2_KG_KMOL,
    MW_CO_KG_KMOL,
    MW_H2O_KG_KMOL,
    MW_N2_KG_KMOL,
    MW_NO2_KG_KMOL,
    MW_NO_KG_KMOL,
    MW_O2_KG_KMOL,
    THC_LOW_SIGNAL_WARN_PPM,
)
from ._airflow import _airflow_component_fraction


def _as_numeric_series(value: object, index: pd.Index) -> pd.Series:
    if isinstance(value, pd.Series):
        return pd.to_numeric(value.reindex(index), errors="coerce")
    return pd.to_numeric(pd.Series(value, index=index, dtype="float64"), errors="coerce")


def _percent_to_fraction(value: object, index: pd.Index) -> pd.Series:
    return _as_numeric_series(value, index) / 100.0


def _ppm_to_fraction(value: object, index: pd.Index) -> pd.Series:
    return _as_numeric_series(value, index) / 1_000_000.0


def _clip_fraction(value: pd.Series, *, lower: float = 0.0, upper: float = 1.0) -> pd.Series:
    s = pd.to_numeric(value, errors="coerce")
    return s.clip(lower=lower, upper=upper)


def _to_str_or_empty(x: object) -> str:
    from ._helpers import _to_str_or_empty as _impl
    return _impl(x)


def specific_emissions_from_analyzer(
    *,
    air_kg_h: object,
    fuel_kg_h: object,
    power_kW: object,
    co2_pct_dry: object,
    co_pct_dry: object,
    o2_pct_dry: object,
    nox_ppm_dry: object,
    thc_ppm_dry: object,
    h2o_wet_frac: object,
    nox_basis: str = "NO",
) -> pd.DataFrame:
    for candidate in (power_kW, air_kg_h, fuel_kg_h, co2_pct_dry, co_pct_dry, o2_pct_dry, nox_ppm_dry, thc_ppm_dry, h2o_wet_frac):
        if isinstance(candidate, pd.Series):
            index = candidate.index
            break
    else:
        raise ValueError("specific_emissions_from_analyzer precisa de pelo menos uma Series para inferir o index.")

    air = _as_numeric_series(air_kg_h, index)
    fuel = _as_numeric_series(fuel_kg_h, index)
    power = _as_numeric_series(power_kW, index)
    co2_dry = _percent_to_fraction(co2_pct_dry, index)
    co_dry = _percent_to_fraction(co_pct_dry, index)
    o2_dry = _percent_to_fraction(o2_pct_dry, index)
    nox_dry = _ppm_to_fraction(nox_ppm_dry, index)
    thc_dry = _ppm_to_fraction(thc_ppm_dry, index)
    h2o_frac = _clip_fraction(_as_numeric_series(h2o_wet_frac, index), lower=0.0, upper=0.999)

    nox_basis_norm = _to_str_or_empty(nox_basis).upper()
    if nox_basis_norm not in {"NO", "NO2"}:
        raise ValueError(f"nox_basis invalido: {nox_basis}")
    mw_nox = MW_NO_KG_KMOL if nox_basis_norm == "NO" else MW_NO2_KG_KMOL

    co2_dry_mix = _clip_fraction(co2_dry)
    co_dry_mix = _clip_fraction(co_dry)
    o2_dry_mix = _clip_fraction(o2_dry)
    nox_dry_mix = _clip_fraction(nox_dry)
    thc_dry_mix = _clip_fraction(thc_dry, lower=0.0)
    dry_known_sum = co2_dry_mix + co_dry_mix + o2_dry_mix + nox_dry_mix + thc_dry_mix
    n2_dry = (1.0 - dry_known_sum).clip(lower=0.0)

    mw_dry = (
        co2_dry_mix * MW_CO2_KG_KMOL
        + co_dry_mix * MW_CO_KG_KMOL
        + o2_dry_mix * MW_O2_KG_KMOL
        + nox_dry_mix * mw_nox
        + thc_dry_mix * MW_C3H8_KG_KMOL
        + n2_dry * MW_N2_KG_KMOL
    )

    exhaust_kg_h = air + fuel
    exhaust_dry_kg_h = exhaust_kg_h * (1.0 - h2o_frac)
    dry_kmol_h = exhaust_dry_kg_h / mw_dry
    wet_kmol_h = dry_kmol_h / (1.0 - h2o_frac)
    h2o_kmol_h = wet_kmol_h * h2o_frac
    mw_wet = (1.0 - h2o_frac) * mw_dry + h2o_frac * MW_H2O_KG_KMOL

    co2_wet = co2_dry * (1.0 - h2o_frac)
    co_wet = co_dry * (1.0 - h2o_frac)
    o2_wet = o2_dry * (1.0 - h2o_frac)
    nox_wet = nox_dry * (1.0 - h2o_frac)
    thc_wet = thc_dry * (1.0 - h2o_frac)
    n2_wet = n2_dry * (1.0 - h2o_frac)

    def _mass_fraction(x_wet: pd.Series, mw_species: float) -> pd.Series:
        return (x_wet * mw_species / mw_wet).where(mw_wet.gt(0), pd.NA)

    co2_mass_frac = _mass_fraction(co2_wet, MW_CO2_KG_KMOL)
    co_mass_frac = _mass_fraction(co_wet, MW_CO_KG_KMOL)
    nox_mass_frac = _mass_fraction(nox_wet, mw_nox)
    thc_mass_frac = _mass_fraction(thc_wet, MW_C3H8_KG_KMOL)

    dry_valid = exhaust_kg_h.gt(0) & mw_dry.gt(0)
    valid_specific = dry_valid & power.gt(0) & mw_wet.gt(0) & h2o_frac.notna()

    def _g_h(mass_fraction: pd.Series) -> pd.Series:
        return (mass_fraction * exhaust_kg_h * 1000.0).where(valid_specific, pd.NA)

    co2_g_h = _g_h(co2_mass_frac)
    co_g_h = _g_h(co_mass_frac)
    nox_g_h = _g_h(nox_mass_frac)
    thc_g_h = _g_h(thc_mass_frac)

    out = pd.DataFrame(index=index)
    out["CO2_dry_frac"] = co2_dry
    out["CO_dry_frac"] = co_dry
    out["O2_dry_frac"] = o2_dry
    out["NOx_dry_frac"] = nox_dry
    out["THC_dry_frac"] = thc_dry
    out["N2_dry_frac"] = n2_dry
    out["CO2_wet_frac"] = co2_wet
    out["CO_wet_frac"] = co_wet
    out["O2_wet_frac"] = o2_wet
    out["NOx_wet_frac"] = nox_wet
    out["THC_wet_frac"] = thc_wet
    out["N2_wet_frac"] = n2_wet
    out["MW_dry_kg_kmol"] = mw_dry.where(dry_valid, pd.NA)
    out["MW_wet_kg_kmol"] = mw_wet.where(valid_specific, pd.NA)
    out["Exhaust_kg_h"] = exhaust_kg_h.where(exhaust_kg_h.gt(0), pd.NA)
    out["Exhaust_Dry_kg_h"] = exhaust_dry_kg_h.where(dry_valid, pd.NA)
    out["Exhaust_Dry_kmol_h"] = dry_kmol_h.where(dry_valid, pd.NA)
    out["Exhaust_H2O_kmol_h"] = h2o_kmol_h.where(valid_specific, pd.NA)
    out["CO2_g_h"] = co2_g_h
    out["CO_g_h"] = co_g_h
    out["NOx_g_h"] = nox_g_h
    out["THC_g_h"] = thc_g_h
    out["CO2_g_kWh"] = (co2_g_h / power).where(valid_specific, pd.NA)
    out["CO_g_kWh"] = (co_g_h / power).where(valid_specific, pd.NA)
    out["NOx_g_kWh"] = (nox_g_h / power).where(valid_specific, pd.NA)
    out["THC_g_kWh"] = (thc_g_h / power).where(valid_specific, pd.NA)
    return out


def _resolve_intake_humidity_ratio_for_emissions(
    df: pd.DataFrame,
    defaults_cfg: Optional[Dict[str, str]] = None,
) -> Tuple[pd.Series, str]:
    t_amb_col = _resolve_existing_column(df, "T_AMBIENTE_mean_of_windows", ["t_ambiente", "amb"])
    rh_col = _resolve_existing_column(df, "UMIDADE_mean_of_windows", ["umidade"])
    p_baro_col = _resolve_existing_column(df, "P_BARO_mean_of_windows", ["p_baro", "baro"])
    default_pressure_kpa = _to_float(
        (defaults_cfg or {}).get(norm_key("VOL_EFF_REF_PRESSURE_kPa"), ""), default=101.3,
    )
    pressure = (
        pd.to_numeric(df[p_baro_col], errors="coerce")
        if p_baro_col
        else pd.Series(default_pressure_kpa, index=df.index, dtype="float64")
    )
    pressure_source = "P_BARO"
    pressure_valid = pressure.dropna()
    if not pressure_valid.empty and float(pressure_valid.median()) > 200.0:
        pressure = pressure / 10.0
        pressure_source = "P_BARO_mbar->kPa"
    if t_amb_col and rh_col:
        return _humidity_ratio_w_from_rh(df[t_amb_col], df[rh_col], pressure), f"T_AMBIENTE+UMIDADE+{pressure_source}"
    if rh_col:
        t_e_comp_col = _resolve_existing_column(df, "T_E_COMP_mean_of_windows", ["t_e_comp"])
        if t_e_comp_col:
            return _humidity_ratio_w_from_rh(df[t_e_comp_col], df[rh_col], pressure), f"T_E_COMP+UMIDADE+{pressure_source}"
    return pd.Series(0.0, index=df.index, dtype="float64"), "fallback_seco"


def add_specific_emissions_channels_inplace(
    df: pd.DataFrame,
    *,
    power_kW: pd.Series,
    fuel_kg_h: pd.Series,
    defaults_cfg: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    out = df.copy()
    idx = out.index
    air_kg_h = pd.to_numeric(out.get("Air_kg_h", pd.Series(pd.NA, index=idx)), errors="coerce")
    fuel_kg_h = pd.to_numeric(fuel_kg_h.reindex(idx), errors="coerce")
    power_kW = pd.to_numeric(power_kW.reindex(idx), errors="coerce")

    dies_frac = _airflow_component_fraction(out, "DIES_pct").fillna(0.0)
    biod_frac = _airflow_component_fraction(out, "BIOD_pct").fillna(0.0)
    etoh_frac = _airflow_component_fraction(out, "EtOH_pct").fillna(0.0)
    fuel_h2o_frac = _airflow_component_fraction(out, "H2O_pct").fillna(0.0)

    intake_humidity_ratio, humidity_source = _resolve_intake_humidity_ratio_for_emissions(out, defaults_cfg)
    intake_humidity_ratio = pd.to_numeric(intake_humidity_ratio, errors="coerce").clip(lower=0.0)
    air_h2o_kg_h = (air_kg_h * intake_humidity_ratio / (1.0 + intake_humidity_ratio)).where(air_kg_h.gt(0), pd.NA)
    fuel_h2o_kg_h = (fuel_kg_h * fuel_h2o_frac).where(fuel_kg_h.ge(0), pd.NA)

    fuel_h_mass_frac = (
        dies_frac * H_MASS_FRAC_DIESEL
        + biod_frac * H_MASS_FRAC_BIODIESEL
        + etoh_frac * H_MASS_FRAC_ETHANOL
    )
    fuel_h_kg_h = (fuel_kg_h * fuel_h_mass_frac).where(fuel_kg_h.ge(0), pd.NA)
    combustion_h2o_kg_h = fuel_h_kg_h * 9.0

    exhaust_kg_h = air_kg_h + fuel_kg_h
    exhaust_h2o_kg_h = air_h2o_kg_h + fuel_h2o_kg_h + combustion_h2o_kg_h
    exhaust_dry_kg_h = exhaust_kg_h - exhaust_h2o_kg_h

    out["Intake_Humidity_Ratio_kgkg"] = intake_humidity_ratio
    out["Intake_Air_H2O_kg_h"] = air_h2o_kg_h
    out["Fuel_H2O_kg_h"] = fuel_h2o_kg_h
    out["Fuel_H_kg_h"] = fuel_h_kg_h
    out["Combustion_H2O_kg_h"] = combustion_h2o_kg_h
    out["Exhaust_H2O_kg_h"] = exhaust_h2o_kg_h
    out["Exhaust_Dry_kg_h"] = exhaust_dry_kg_h

    co2_col = _resolve_existing_column(out, "CO2_mean_of_windows", ["co2"])
    co_col = _resolve_existing_column(out, "CO_mean_of_windows", ["co"])
    o2_col = _resolve_existing_column(out, "O2_mean_of_windows", ["o2"])
    nox_col = _resolve_existing_column(out, "NOX_mean_of_windows", ["nox"])
    thc_col = _resolve_existing_column(out, "THC_mean_of_windows", ["thc"])

    co2 = pd.to_numeric(out.get(co2_col, pd.Series(pd.NA, index=idx)), errors="coerce")
    co = pd.to_numeric(out.get(co_col, pd.Series(pd.NA, index=idx)), errors="coerce")
    o2 = pd.to_numeric(out.get(o2_col, pd.Series(pd.NA, index=idx)), errors="coerce")
    nox = pd.to_numeric(out.get(nox_col, pd.Series(pd.NA, index=idx)), errors="coerce")
    thc = pd.to_numeric(out.get(thc_col, pd.Series(pd.NA, index=idx)), errors="coerce")

    low_thc_mask = thc.abs().lt(THC_LOW_SIGNAL_WARN_PPM)
    negative_thc_mask = thc.lt(0)
    out["THC_LOW_SIGNAL_FLAG"] = low_thc_mask.astype("Int64")
    out["THC_NEGATIVE_FLAG"] = negative_thc_mask.astype("Int64")

    emissions_ref = specific_emissions_from_analyzer(
        air_kg_h=air_kg_h, fuel_kg_h=fuel_kg_h, power_kW=power_kW,
        co2_pct_dry=co2, co_pct_dry=co, o2_pct_dry=o2,
        nox_ppm_dry=nox, thc_ppm_dry=thc,
        h2o_wet_frac=pd.Series(np.nan, index=idx, dtype="float64"),
        nox_basis="NO",
    )

    dry_valid = pd.to_numeric(emissions_ref["MW_dry_kg_kmol"], errors="coerce").gt(0)
    h2o_wet_frac = (
        pd.to_numeric(exhaust_h2o_kg_h, errors="coerce") / MW_H2O_KG_KMOL
    ) / (
        (pd.to_numeric(exhaust_h2o_kg_h, errors="coerce") / MW_H2O_KG_KMOL)
        + (pd.to_numeric(exhaust_dry_kg_h, errors="coerce") / pd.to_numeric(emissions_ref["MW_dry_kg_kmol"], errors="coerce"))
    )
    h2o_wet_frac = h2o_wet_frac.where(dry_valid & exhaust_dry_kg_h.gt(0) & exhaust_h2o_kg_h.ge(0), pd.NA)
    h2o_wet_frac = h2o_wet_frac.clip(lower=0.0, upper=0.999)
    out["H2O_wet_frac"] = h2o_wet_frac

    emissions_no = specific_emissions_from_analyzer(
        air_kg_h=air_kg_h, fuel_kg_h=fuel_kg_h, power_kW=power_kW,
        co2_pct_dry=co2, co_pct_dry=co, o2_pct_dry=o2,
        nox_ppm_dry=nox, thc_ppm_dry=thc,
        h2o_wet_frac=h2o_wet_frac, nox_basis="NO",
    )
    emissions_no2 = specific_emissions_from_analyzer(
        air_kg_h=air_kg_h, fuel_kg_h=fuel_kg_h, power_kW=power_kW,
        co2_pct_dry=co2, co_pct_dry=co, o2_pct_dry=o2,
        nox_ppm_dry=nox, thc_ppm_dry=thc,
        h2o_wet_frac=h2o_wet_frac, nox_basis="NO2",
    )

    shared_cols = [
        "CO2_dry_frac", "CO_dry_frac", "O2_dry_frac", "NOx_dry_frac", "THC_dry_frac", "N2_dry_frac",
        "CO2_wet_frac", "CO_wet_frac", "O2_wet_frac", "NOx_wet_frac", "THC_wet_frac", "N2_wet_frac",
        "MW_dry_kg_kmol", "MW_wet_kg_kmol",
        "Exhaust_kg_h", "Exhaust_Dry_kg_h", "Exhaust_Dry_kmol_h", "Exhaust_H2O_kmol_h",
        "CO2_g_h", "CO_g_h", "THC_g_h", "CO2_g_kWh", "CO_g_kWh", "THC_g_kWh",
    ]
    for column in shared_cols:
        out[column] = emissions_no[column]

    out["MW_dry_kg_kmol_as_NO"] = emissions_no["MW_dry_kg_kmol"]
    out["MW_wet_kg_kmol_as_NO"] = emissions_no["MW_wet_kg_kmol"]
    out["MW_dry_kg_kmol_as_NO2"] = emissions_no2["MW_dry_kg_kmol"]
    out["MW_wet_kg_kmol_as_NO2"] = emissions_no2["MW_wet_kg_kmol"]
    out["NOx_g_h_as_NO"] = emissions_no["NOx_g_h"]
    out["NOx_g_kWh_as_NO"] = emissions_no["NOx_g_kWh"]
    out["NOx_g_h_as_NO2"] = emissions_no2["NOx_g_h"]
    out["NOx_g_kWh_as_NO2"] = emissions_no2["NOx_g_kWh"]
    out["NOx_as_NO_g_kWh"] = emissions_no["NOx_g_kWh"]
    out["NOx_as_NO2_g_kWh"] = emissions_no2["NOx_g_kWh"]
    out["EMISSIONS_H2O_SOURCE"] = humidity_source
    return out
