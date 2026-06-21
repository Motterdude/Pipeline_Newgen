"""Evaporative cooling metrics and Net Energy Factor (NEF) calculations.

Adds columns for:
- Evaporative potential (h_fg blend, Qdot_evap_pot)
- Evaporative-cooling effectiveness
- Net Energy Factor (Fagundez et al.)
- Sanity flags
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from .constants import K_COVERAGE

# ---------------------------------------------------------------------------
# Thermodynamic constants at 298.15 K
# ---------------------------------------------------------------------------
H_FG_ETHANOL_298K_KJ_KG = 918.3   # NIST WebBook, 42.3 kJ/mol / 0.04607
H_FG_WATER_298K_KJ_KG = 2441.7    # IAPWS, 43.99 kJ/mol / 0.018015

# Pure component densities at 20 °C (for mass-to-volume conversion)
RHO_ETHANOL_KG_M3 = 789.0
RHO_WATER_KG_M3 = 998.0

# Fagundez et al. ED data (ethanol vol% → distillation energy MJ/kg)
_FAGUNDEZ_ETHANOL_VV_PCT = np.array([61.68, 70.60, 81.53, 90.41, 93.72])
_FAGUNDEZ_ED_MJ_KG = np.array([14.74, 17.66, 25.77, 34.75, 89.83])


# ---------------------------------------------------------------------------
# Latent heat correlations
# ---------------------------------------------------------------------------

def _h_fg_ethanol_kj_kg(T_K: pd.Series) -> pd.Series:
    """Enthalpy of vaporization of ethanol using Watson correlation.

    Watson: h_fg(T) = h_fg_ref * ((Tc - T) / (Tc - T_ref))^n
    Tc_ethanol = 513.9 K, T_ref = 298.15 K, n = 0.38
    """
    Tc = 513.9
    T_ref = 298.15
    n = 0.38
    ratio = ((Tc - T_K) / (Tc - T_ref)).clip(lower=0.0)
    return H_FG_ETHANOL_298K_KJ_KG * ratio ** n


def _h_fg_water_kj_kg(T_K: pd.Series) -> pd.Series:
    """Enthalpy of vaporization of water using Watson correlation.

    Tc_water = 647.1 K, T_ref = 298.15 K, n = 0.38
    """
    Tc = 647.1
    T_ref = 298.15
    n = 0.38
    ratio = ((Tc - T_K) / (Tc - T_ref)).clip(lower=0.0)
    return H_FG_WATER_298K_KJ_KG * ratio ** n


# ---------------------------------------------------------------------------
# NEF helpers
# ---------------------------------------------------------------------------

def _ethanol_mass_to_vol_pct(Y_ethanol: pd.Series, Y_water: pd.Series) -> pd.Series:
    """Convert ethanol/water mass fractions to ethanol volume percent.

    V_eth = Y_eth / rho_eth; V_w = Y_w / rho_w
    ethanol_vv_pct = V_eth / (V_eth + V_w) * 100
    """
    V_eth = Y_ethanol / RHO_ETHANOL_KG_M3
    V_w = Y_water / RHO_WATER_KG_M3
    total_v = V_eth + V_w
    return (V_eth / total_v * 100.0).where(total_v > 0, pd.NA)


def _interpolate_ED_mj_kg(ethanol_vv_pct: pd.Series) -> pd.Series:
    """Interpolate distillation energy from Fagundez et al. data.

    Linear interpolation within range. Above max (93.72%), clamp to
    the HEF value (89.83 MJ/kg) — linear extrapolation is physically
    wrong near the ethanol-water azeotrope where ED diverges.
    Below min (61.68%), return NaN.
    """
    x = ethanol_vv_pct.values.astype(float)
    result = np.interp(
        x, _FAGUNDEZ_ETHANOL_VV_PCT, _FAGUNDEZ_ED_MJ_KG, left=np.nan
    )
    above_mask = x > _FAGUNDEZ_ETHANOL_VV_PCT[-1]
    result[above_mask] = _FAGUNDEZ_ED_MJ_KG[-1]
    return pd.Series(result, index=ethanol_vv_pct.index)


# ---------------------------------------------------------------------------
# Main attachment functions
# ---------------------------------------------------------------------------

def _resolve_fuel_kgh(df: pd.DataFrame) -> pd.Series:
    """Resolve fuel mass flow column (kg/h) by priority."""
    for cand in ["Consumo_kg_h", "Consumo_kg_h_mean_of_windows", "Fuel_kg_h"]:
        if cand in df.columns:
            return pd.to_numeric(df[cand], errors="coerce")
    return pd.Series(pd.NA, index=df.index, dtype="Float64")


def attach_evaporative_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add evaporative cooling potential columns and sanity flags."""

    PkW = pd.to_numeric(df.get("UPD_Power_kW", pd.NA), errors="coerce")
    Fkgh = _resolve_fuel_kgh(df)
    etoh_pct = pd.to_numeric(df.get("EtOH_pct", pd.NA), errors="coerce")
    h2o_pct = pd.to_numeric(df.get("H2O_pct", pd.NA), errors="coerce")

    t_adm_col = None
    for cand in ["T_ADMISSAO_mean_of_windows", "T_ADMISSAO"]:
        if cand in df.columns:
            t_adm_col = cand
            break
    t_scil_col = None
    for cand in ["T_S_CIL_mean_of_windows", "T_E_CIL_AVG_mean_of_windows"]:
        if cand in df.columns:
            t_scil_col = cand
            break

    T_adm = pd.to_numeric(df[t_adm_col], errors="coerce") if t_adm_col else pd.Series(pd.NA, index=df.index)
    T_scil = pd.to_numeric(df[t_scil_col], errors="coerce") if t_scil_col else pd.Series(pd.NA, index=df.index)

    # Mass fractions (0..1)
    Y_e = etoh_pct / 100.0
    Y_w = h2o_pct / 100.0
    is_ethanol_fuel = etoh_pct.gt(0)

    # delta_T: T_S_CIL - T_ADMISSAO (negative = cooling)
    delta_T_air_K = T_scil - T_adm
    df["delta_T_air_K"] = delta_T_air_K

    # q_air_cool per kWh: reuse existing Q_EVAP_NET_kW
    Q_air_cool = pd.to_numeric(df.get("Q_EVAP_NET_kW", pd.NA), errors="coerce")
    q_air_cool_kJ_kWh = (3600.0 * Q_air_cool / PkW).where(PkW.gt(0), pd.NA)
    df["q_air_cool_kJ_kWh"] = q_air_cool_kJ_kWh

    # Evaporative reference temperature
    T_evap_ref_C = (T_adm + T_scil) / 2.0
    T_evap_ref_K = T_evap_ref_C + 273.15
    df["T_evap_ref_K"] = T_evap_ref_K.where(is_ethanol_fuel, pd.NA)

    # Latent heats
    h_fg_eth = _h_fg_ethanol_kj_kg(T_evap_ref_K)
    h_fg_w = _h_fg_water_kj_kg(T_evap_ref_K)
    df["h_fg_ethanol_kJ_kg"] = h_fg_eth.where(is_ethanol_fuel, pd.NA)
    df["h_fg_water_kJ_kg"] = h_fg_w.where(is_ethanol_fuel, pd.NA)

    # Blend latent heat
    h_fg_blend = Y_e * h_fg_eth + Y_w * h_fg_w
    df["h_fg_blend_kJ_kg"] = h_fg_blend.where(is_ethanol_fuel, pd.NA)

    # Evaporative potential power
    mdot_f_kg_s = Fkgh / 3600.0
    Qdot_evap_pot = mdot_f_kg_s * h_fg_blend
    df["Qdot_evap_pot_kW"] = Qdot_evap_pot.where(is_ethanol_fuel, pd.NA)

    # Evaporative potential per kWh
    q_evap_pot = (3600.0 * Qdot_evap_pot / PkW).where(PkW.gt(0), pd.NA)
    df["q_evap_pot_kJ_kWh"] = q_evap_pot.where(is_ethanol_fuel, pd.NA)

    # Evaporative-cooling effectiveness
    # Use absolute value of Q_air_cool (cooling is negative in our convention)
    # effectiveness = |Q_air_cool| / Q_evap_pot
    evap_eff = (Q_air_cool.abs() / Qdot_evap_pot).where(
        is_ethanol_fuel & Qdot_evap_pot.gt(0), pd.NA
    )
    df["evap_cooling_effectiveness"] = evap_eff

    # --- Manifold / chamber evaporative split ---
    # Q_manifold = heat already absorbed by evaporation in the intake manifold
    # (measured as air cooling; for diesel = 0 by definition)
    Q_manifold = Q_air_cool.abs().where(is_ethanol_fuel & Q_air_cool.lt(0), 0.0)
    df["Q_manifold_evap_kW"] = Q_manifold.where(is_ethanol_fuel, pd.NA)

    # Q_chamber = latent potential remaining for in-cylinder charge cooling
    Q_chamber = (Qdot_evap_pot - Q_manifold).clip(lower=0.0)
    df["Q_chamber_available_kW"] = Q_chamber.where(is_ethanol_fuel, pd.NA)

    # Specific versions (kJ per kWh electric)
    df["q_manifold_evap_kJ_kWh"] = (3600.0 * Q_manifold / PkW).where(
        is_ethanol_fuel & PkW.gt(0), pd.NA
    )
    df["q_chamber_available_kJ_kWh"] = (3600.0 * Q_chamber / PkW).where(
        is_ethanol_fuel & PkW.gt(0), pd.NA
    )

    # --- Sanity flags ---
    flags = pd.Series("", index=df.index, dtype="object")
    flag_dt_pos = is_ethanol_fuel & delta_T_air_K.gt(0)
    flag_eff_neg = is_ethanol_fuel & evap_eff.lt(0)
    flag_eff_high = is_ethanol_fuel & evap_eff.gt(1.2)
    flags = flags.where(~flag_dt_pos, flags + "dT>0_no_cooling;")
    flags = flags.where(~flag_eff_neg, flags + "eff<0_invalid;")
    flags = flags.where(~flag_eff_high, flags + "eff>1.2_review;")
    df["evap_sanity_flags"] = flags.where(is_ethanol_fuel, "N/A_diesel")

    return df


def attach_nef_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add Net Energy Factor columns (Fagundez et al. method)."""

    etoh_pct = pd.to_numeric(df.get("EtOH_pct", pd.NA), errors="coerce")
    h2o_pct = pd.to_numeric(df.get("H2O_pct", pd.NA), errors="coerce")
    LHV_kJ_kg = pd.to_numeric(df.get("LHV_kJ_kg", pd.NA), errors="coerce")
    n_th = pd.to_numeric(df.get("n_th", pd.NA), errors="coerce")
    PkW = pd.to_numeric(df.get("UPD_Power_kW", pd.NA), errors="coerce")
    Fkgh = _resolve_fuel_kgh(df)

    is_ethanol_fuel = etoh_pct.gt(0)

    # Mass fractions → volume percent for ED interpolation
    Y_e = etoh_pct / 100.0
    Y_w = h2o_pct / 100.0
    ethanol_vv_pct = _ethanol_mass_to_vol_pct(Y_e, Y_w)
    df["ethanol_vv_pct_for_ED"] = ethanol_vv_pct.where(is_ethanol_fuel, pd.NA)

    # Interpolate ED
    ED_MJ_kg = _interpolate_ED_mj_kg(ethanol_vv_pct)
    df["ED_MJ_kg"] = ED_MJ_kg.where(is_ethanol_fuel, pd.NA)

    # NEF_chem = LHV_MJ / ED_MJ
    LHV_MJ_kg = LHV_kJ_kg / 1000.0
    NEF_chem = (LHV_MJ_kg / ED_MJ_kg).where(is_ethanol_fuel & ED_MJ_kg.gt(0), pd.NA)
    df["NEF_chem"] = NEF_chem

    # NEF_e = eta_f * LHV_MJ / ED_MJ  (equivalent: 3.6 * P_e / (mdot * ED))
    NEF_e = (n_th * LHV_MJ_kg / ED_MJ_kg).where(
        is_ethanol_fuel & ED_MJ_kg.gt(0) & n_th.gt(0), pd.NA
    )
    df["NEF_e"] = NEF_e

    # Flag if ethanol_vv_pct is outside Fagundez range
    outside_range = is_ethanol_fuel & (
        (ethanol_vv_pct < _FAGUNDEZ_ETHANOL_VV_PCT[0]) |
        (ethanol_vv_pct > _FAGUNDEZ_ETHANOL_VV_PCT[-1])
    )
    df["NEF_flag"] = ""
    df.loc[outside_range, "NEF_flag"] = "ED_extrapolated_outside_Fagundez_range"
    df.loc[~is_ethanol_fuel, "NEF_flag"] = "N/A_diesel"

    return df
