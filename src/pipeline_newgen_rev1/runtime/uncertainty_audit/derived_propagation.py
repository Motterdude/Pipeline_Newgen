"""Propagação nativa de uA/uB para grandezas derivadas que hoje só têm uc.

Para cada derivada coberta pelo audit layer, este módulo implementa a lei de
propagação de incerteza (GUM §5) **separadamente** para uA e uB, permitindo
o cálculo de %contribuição variance-weighted downstream.

Convenção: todas as funções recebem o `final_table` inteiro (DataFrame) e retornam
um dict com as colunas que o audit layer deve gravar (uA_<m>, uB_<m>).
Se as colunas já existem no `final_table` (caso legado drifted), o audit layer
pode optar por preservá-las e não sobrescrever.
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd


def _safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    """num/den protegido contra divisão por zero ou NaN."""
    num_n = pd.to_numeric(num, errors="coerce")
    den_n = pd.to_numeric(den, errors="coerce")
    safe_den = den_n.where(den_n.abs() > 0, pd.NA)
    return num_n / safe_den


def propagate_consumo_L_h(final_table: pd.DataFrame) -> Dict[str, pd.Series]:
    """Consumo_L_h = Consumo_kg_h / Fuel_Density_kg_m3 · 1000

    uA_L_h = Consumo_L_h · |uA_Consumo_kg_h / Consumo_kg_h|    (density é uB-only)
    uB_L_h = Consumo_L_h · √((uB_Consumo_kg_h/Consumo_kg_h)² + (uB_density/density)²)
    """
    val = pd.to_numeric(final_table.get("Consumo_L_h", pd.NA), errors="coerce")
    fuel = pd.to_numeric(final_table.get("Consumo_kg_h_mean_of_windows", pd.NA), errors="coerce")
    uA_fuel = pd.to_numeric(final_table.get("uA_Consumo_kg_h", pd.NA), errors="coerce")
    uB_fuel = pd.to_numeric(final_table.get("uB_Consumo_kg_h", pd.NA), errors="coerce")
    # Densidade: uB_density é opcional; se não existir, uB_density=0 (conservador).
    density = pd.to_numeric(final_table.get("Fuel_Density_kg_m3", pd.NA), errors="coerce")
    uB_density = pd.to_numeric(final_table.get("uB_Fuel_Density_kg_m3", pd.Series(0.0, index=val.index)), errors="coerce").fillna(0.0)

    rel_uA_sq = _safe_ratio(uA_fuel, fuel) ** 2
    rel_uB_sq = _safe_ratio(uB_fuel, fuel) ** 2 + _safe_ratio(uB_density, density) ** 2

    uA = val.abs() * np.sqrt(rel_uA_sq)
    uB = val.abs() * np.sqrt(rel_uB_sq)
    return {"uA_Consumo_L_h": uA, "uB_Consumo_L_h": uB}


def propagate_n_th(final_table: pd.DataFrame) -> Dict[str, pd.Series]:
    """η_th = P / (ṁ · LHV)   → P em kW, ṁ em kg/h, LHV em kJ/kg (legado convert internamente).

    uA_n_th = n_th · √((uA_P/P)² + (uA_ṁ/ṁ)²)             (LHV é uB-only tipicamente)
    uB_n_th = n_th · √((uB_P/P)² + (uB_ṁ/ṁ)² + (uB_LHV/LHV)²)
    """
    val = pd.to_numeric(final_table.get("n_th", pd.NA), errors="coerce")
    P = pd.to_numeric(final_table.get("Potência Total_mean_of_windows", pd.NA), errors="coerce")
    uA_P = pd.to_numeric(final_table.get("uA_P_kw", pd.NA), errors="coerce")
    uB_P = pd.to_numeric(final_table.get("uB_P_kw", pd.NA), errors="coerce")
    m_dot = pd.to_numeric(final_table.get("Consumo_kg_h_mean_of_windows", pd.NA), errors="coerce")
    uA_m = pd.to_numeric(final_table.get("uA_Consumo_kg_h", pd.NA), errors="coerce")
    uB_m = pd.to_numeric(final_table.get("uB_Consumo_kg_h", pd.NA), errors="coerce")
    LHV = pd.to_numeric(final_table.get("LHV_kJ_kg", pd.NA), errors="coerce")
    uB_LHV = pd.to_numeric(final_table.get("uB_LHV_kJ_kg", pd.Series(0.0, index=val.index)), errors="coerce").fillna(0.0)

    rel_uA_sq = _safe_ratio(uA_P, P) ** 2 + _safe_ratio(uA_m, m_dot) ** 2
    rel_uB_sq = _safe_ratio(uB_P, P) ** 2 + _safe_ratio(uB_m, m_dot) ** 2 + _safe_ratio(uB_LHV, LHV) ** 2

    uA = val.abs() * np.sqrt(rel_uA_sq)
    uB = val.abs() * np.sqrt(rel_uB_sq)
    # Em unidade percentual (n_th_pct = n_th·100): as incertezas também escalam por 100.
    return {
        "uA_n_th": uA,
        "uB_n_th": uB,
        "uA_n_th_pct": uA * 100.0,
        "uB_n_th_pct": uB * 100.0,
    }


def propagate_bsfc(final_table: pd.DataFrame) -> Dict[str, pd.Series]:
    """BSFC = ṁ · 1000 / P     [g/kWh com ṁ em kg/h, P em kW]

    uA_BSFC = BSFC · √((uA_ṁ/ṁ)² + (uA_P/P)²)
    uB_BSFC = BSFC · √((uB_ṁ/ṁ)² + (uB_P/P)²)
    """
    val = pd.to_numeric(final_table.get("BSFC_g_kWh", pd.NA), errors="coerce")
    P = pd.to_numeric(final_table.get("Potência Total_mean_of_windows", pd.NA), errors="coerce")
    uA_P = pd.to_numeric(final_table.get("uA_P_kw", pd.NA), errors="coerce")
    uB_P = pd.to_numeric(final_table.get("uB_P_kw", pd.NA), errors="coerce")
    m_dot = pd.to_numeric(final_table.get("Consumo_kg_h_mean_of_windows", pd.NA), errors="coerce")
    uA_m = pd.to_numeric(final_table.get("uA_Consumo_kg_h", pd.NA), errors="coerce")
    uB_m = pd.to_numeric(final_table.get("uB_Consumo_kg_h", pd.NA), errors="coerce")

    rel_uA_sq = _safe_ratio(uA_P, P) ** 2 + _safe_ratio(uA_m, m_dot) ** 2
    rel_uB_sq = _safe_ratio(uB_P, P) ** 2 + _safe_ratio(uB_m, m_dot) ** 2

    uA = val.abs() * np.sqrt(rel_uA_sq)
    uB = val.abs() * np.sqrt(rel_uB_sq)
    return {"uA_BSFC_g_kWh": uA, "uB_BSFC_g_kWh": uB}


def propagate_emission_gkwh(
    final_table: pd.DataFrame,
    *,
    value_col: str,
    conc_col_mean: str,
    conc_prefix: str,
) -> Dict[str, pd.Series]:
    """Emissão específica (CO_g_kWh, CO2_g_kWh, NOx_g_kWh, THC_g_kWh) → propagação RSS relativa.

    Para qualquer emissão E_g_kWh = concentração · fluxo / P (com fatores moleculares/pressão/etc.):
    uA_E = |E| · √((uA_conc/conc)² + (uA_P/P)² + (uA_ṁ/ṁ)²)
    uB_E = |E| · √((uB_conc/conc)² + (uB_P/P)² + (uB_ṁ/ṁ)²)

    Se `uA_<value_col>` já existir em `final_table` (legado drifted), preserva.
    """
    val = pd.to_numeric(final_table.get(value_col, pd.NA), errors="coerce")
    if val.isna().all():
        empty = pd.Series([pd.NA] * len(final_table), index=final_table.index, dtype="float64")
        return {f"uA_{value_col}": empty, f"uB_{value_col}": empty}

    conc = pd.to_numeric(final_table.get(conc_col_mean, pd.NA), errors="coerce")
    uA_conc = pd.to_numeric(final_table.get(f"uA_{conc_prefix}", pd.NA), errors="coerce")
    uB_conc = pd.to_numeric(final_table.get(f"uB_{conc_prefix}", pd.NA), errors="coerce")
    P = pd.to_numeric(final_table.get("Potência Total_mean_of_windows", pd.NA), errors="coerce")
    uA_P = pd.to_numeric(final_table.get("uA_P_kw", pd.NA), errors="coerce")
    uB_P = pd.to_numeric(final_table.get("uB_P_kw", pd.NA), errors="coerce")
    m_dot = pd.to_numeric(final_table.get("Consumo_kg_h_mean_of_windows", pd.NA), errors="coerce")
    uA_m = pd.to_numeric(final_table.get("uA_Consumo_kg_h", pd.NA), errors="coerce")
    uB_m = pd.to_numeric(final_table.get("uB_Consumo_kg_h", pd.NA), errors="coerce")

    rel_uA_sq = _safe_ratio(uA_conc, conc) ** 2 + _safe_ratio(uA_P, P) ** 2 + _safe_ratio(uA_m, m_dot) ** 2
    rel_uB_sq = _safe_ratio(uB_conc, conc) ** 2 + _safe_ratio(uB_P, P) ** 2 + _safe_ratio(uB_m, m_dot) ** 2

    uA = val.abs() * np.sqrt(rel_uA_sq)
    uB = val.abs() * np.sqrt(rel_uB_sq)
    return {f"uA_{value_col}": uA, f"uB_{value_col}": uB}
