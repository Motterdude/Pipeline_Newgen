"""E94H6 machine scenario projections (annual cost/savings vs diesel)."""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from ._fuel_defaults import _fuel_blend_labels
from ._helpers import _to_float, norm_key
from .constants import MACHINE_SCENARIO_SPECS, SCENARIO_REFERENCE_FUEL_LABEL


def _scenario_machine_col(machine_key: str, suffix: str) -> str:
    return f"Scenario_{machine_key}_{suffix}"


def _resolve_machine_scenario_inputs(
    defaults_cfg: Dict[str, str],
    spec: Dict[str, str],
) -> Tuple[float, float, bool]:
    hours = _to_float(defaults_cfg.get(norm_key(spec["hours_param"]), ""), default=float("nan"))
    diesel_l_h = _to_float(defaults_cfg.get(norm_key(spec["diesel_l_h_param"]), ""), default=float("nan"))
    swapped = False
    if np.isfinite(hours) and np.isfinite(diesel_l_h):
        likely_swapped = (
            (hours < 100.0 and diesel_l_h > 200.0)
            or (hours < 200.0 and diesel_l_h > 1000.0)
        )
        if likely_swapped:
            hours, diesel_l_h = diesel_l_h, hours
            swapped = True
            print(
                f"[WARN] Parametros de maquina parecem invertidos em {spec['label']}: "
                f"{spec['hours_param']}={_to_float(defaults_cfg.get(norm_key(spec['hours_param']), ''), default=float('nan'))}, "
                f"{spec['diesel_l_h_param']}={_to_float(defaults_cfg.get(norm_key(spec['diesel_l_h_param']), ''), default=float('nan'))}. "
                f"Vou usar hours/ano={hours:g} e diesel_L_h={diesel_l_h:g}."
            )
    return hours, diesel_l_h, swapped


def _attach_e94h6_machine_scenario_metrics(
    df: pd.DataFrame,
    defaults_cfg: Dict[str, str],
) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    idx = out.index
    fuel_labels = out.get("Fuel_Label", pd.Series(pd.NA, index=idx, dtype="object"))
    fuel_labels = fuel_labels.where(fuel_labels.notna(), _fuel_blend_labels(out))
    out["Fuel_Label"] = fuel_labels

    scenario_suffixes = [
        "Hours_Ano", "Diesel_L_h", "Diesel_L_ano", "Diesel_Custo_R_h", "Diesel_Custo_R_ano",
        "E94H6_L_h", "U_E94H6_L_h", "E94H6_L_ano", "U_E94H6_L_ano",
        "E94H6_Custo_R_h", "U_E94H6_Custo_R_h", "E94H6_Custo_R_ano", "U_E94H6_Custo_R_ano",
        "Economia_R_h", "U_Economia_R_h", "Economia_R_ano", "U_Economia_R_ano",
    ]
    for spec in MACHINE_SCENARIO_SPECS:
        for suffix in scenario_suffixes:
            col = _scenario_machine_col(spec["key"], suffix)
            if col not in out.columns:
                out[col] = pd.NA

    ref_mask = fuel_labels.eq(SCENARIO_REFERENCE_FUEL_LABEL)
    if not bool(ref_mask.any()):
        print(f"[WARN] Nao encontrei pontos {SCENARIO_REFERENCE_FUEL_LABEL} para os cenarios de maquinas.")
        return out

    diesel_cost_l = _to_float(defaults_cfg.get(norm_key("FUEL_COST_R_L_D85B15"), ""), default=float("nan"))
    ethanol_cost_l = _to_float(defaults_cfg.get(norm_key("FUEL_COST_R_L_E94H6"), ""), default=float("nan"))
    if not (np.isfinite(diesel_cost_l) and diesel_cost_l > 0):
        print("[WARN] FUEL_COST_R_L_D85B15 invalido no Defaults; cenarios de maquinas ficarao vazios.")
        return out
    if not (np.isfinite(ethanol_cost_l) and ethanol_cost_l > 0):
        print("[WARN] FUEL_COST_R_L_E94H6 invalido no Defaults; cenarios de maquinas ficarao vazios.")
        return out

    economia_pct = pd.to_numeric(out.get("Economia_vs_Diesel_pct", pd.NA), errors="coerce")
    U_economia_pct = pd.to_numeric(out.get("U_Economia_vs_Diesel_pct", pd.NA), errors="coerce")
    valid_ref = ref_mask & economia_pct.notna()

    missing_params: List[str] = []
    for spec in MACHINE_SCENARIO_SPECS:
        hours, diesel_l_h, _swapped = _resolve_machine_scenario_inputs(defaults_cfg, spec)
        if not (np.isfinite(hours) and hours > 0):
            missing_params.append(spec["hours_param"])
            continue
        if not (np.isfinite(diesel_l_h) and diesel_l_h > 0):
            missing_params.append(spec["diesel_l_h_param"])
            continue

        ratio_ethanol_vs_diesel = 1.0 + (economia_pct / 100.0)
        valid = valid_ref & ratio_ethanol_vs_diesel.gt(0)
        if not bool(valid.any()):
            continue

        diesel_cost_h = diesel_l_h * diesel_cost_l
        diesel_l_ano = diesel_l_h * hours
        diesel_cost_ano = diesel_cost_h * hours

        ethanol_cost_h = diesel_cost_h * ratio_ethanol_vs_diesel
        U_ethanol_cost_h = diesel_cost_h * (U_economia_pct.abs() / 100.0)
        ethanol_l_h = ethanol_cost_h / ethanol_cost_l
        U_ethanol_l_h = U_ethanol_cost_h / ethanol_cost_l
        ethanol_l_ano = ethanol_l_h * hours
        U_ethanol_l_ano = U_ethanol_l_h * hours
        ethanol_cost_ano = ethanol_cost_h * hours
        U_ethanol_cost_ano = U_ethanol_cost_h * hours
        economia_r_h = ethanol_cost_h - diesel_cost_h
        economia_r_ano = ethanol_cost_ano - diesel_cost_ano

        const_pairs = {
            "Hours_Ano": hours, "Diesel_L_h": diesel_l_h, "Diesel_L_ano": diesel_l_ano,
            "Diesel_Custo_R_h": diesel_cost_h, "Diesel_Custo_R_ano": diesel_cost_ano,
        }
        for suffix, value in const_pairs.items():
            out.loc[valid, _scenario_machine_col(spec["key"], suffix)] = value

        value_pairs = {
            "E94H6_L_h": ethanol_l_h, "U_E94H6_L_h": U_ethanol_l_h,
            "E94H6_L_ano": ethanol_l_ano, "U_E94H6_L_ano": U_ethanol_l_ano,
            "E94H6_Custo_R_h": ethanol_cost_h, "U_E94H6_Custo_R_h": U_ethanol_cost_h,
            "E94H6_Custo_R_ano": ethanol_cost_ano, "U_E94H6_Custo_R_ano": U_ethanol_cost_ano,
            "Economia_R_h": economia_r_h, "U_Economia_R_h": U_ethanol_cost_h,
            "Economia_R_ano": economia_r_ano, "U_Economia_R_ano": U_ethanol_cost_ano,
        }
        for suffix, series in value_pairs.items():
            out.loc[valid, _scenario_machine_col(spec["key"], suffix)] = pd.to_numeric(series, errors="coerce").where(valid, pd.NA)

    if missing_params:
        print(
            "[WARN] Defaults ausentes/invalidos para cenarios de maquinas: "
            + ", ".join(sorted(set(missing_params)))
            + ". As colunas desses cenarios ficarao vazias."
        )
    return out
