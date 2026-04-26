"""Orchestrator: ``build_final_table`` — faithful port of the legacy function.

Reproduces the exact call sequence from the legacy monolith L5361-5832,
delegating to the subpackage modules for each logical block.
"""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ._airflow import (
    _resolve_airflow_lambda_col,
    _resolve_airflow_maf_col,
    add_airflow_channels_prefer_maf_inplace,
)
from ._delta_vs_ref import _attach_delta_vs_ref_metrics
from ._diesel_cost_delta import _attach_diesel_cost_delta_metrics
from ._emissions import add_specific_emissions_channels_inplace
from ._fuel_defaults import (
    _fuel_blend_labels,
    _fuel_default_lookup_series,
    _lookup_lhv_for_blend,
)
from ._helpers import (
    _find_first_col_by_substrings,
    _nan_series,
    _resolve_existing_column,
    _to_float,
    norm_key,
    resolve_col,
)
from ._machine_scenarios import _attach_e94h6_machine_scenario_metrics
from ._merge import _find_kibox_col_by_tokens, _left_merge_on_fuel_keys
from ._psychrometrics import (
    _absolute_humidity_g_m3,
    _cp_air_dry_kj_kgk,
    _cp_moist_air_kj_kgk,
    _humidity_ratio_w_from_rh,
)
from ._reporting import _apply_reporting_rounding
from ._source_identity import add_run_context_columns, add_source_identity_columns
from ._uncertainty_instruments import (
    _combine_average_temperature_uncertainties,
    _combine_delta_temperature_uncertainties,
    add_uncertainties_from_mappings,
)
from ._volumetric_efficiency import add_volumetric_efficiency_from_airflow_method_inplace
from .constants import K_COVERAGE, THC_LOW_SIGNAL_WARN_PPM


def build_final_table(
    ponto: pd.DataFrame,
    fuel_properties: pd.DataFrame,
    kibox_agg: pd.DataFrame,
    motec_ponto: pd.DataFrame,
    mappings: Dict[str, Dict[str, str]],
    instruments: List[Dict[str, Any]],
    reporting: List[Dict[str, Any]],
    defaults: Dict[str, str],
) -> pd.DataFrame:
    mappings = {norm_key(k): v for k, v in mappings.items()}
    instruments_df = pd.DataFrame(instruments) if instruments else pd.DataFrame()
    if not instruments_df.empty and "key" in instruments_df.columns and "key_norm" not in instruments_df.columns:
        instruments_df["key_norm"] = instruments_df["key"].map(norm_key)
    reporting_df = pd.DataFrame(reporting) if reporting else pd.DataFrame()

    if ponto is None or ponto.empty:
        return ponto.copy() if isinstance(ponto, pd.DataFrame) else pd.DataFrame()

    # --- 1. Merge inputs ---
    df = add_source_identity_columns(ponto)
    df = _left_merge_on_fuel_keys(df, fuel_properties)
    if kibox_agg is not None and not kibox_agg.empty:
        df = _left_merge_on_fuel_keys(df, kibox_agg, extra_on=["SourceFolder", "Load_kW"])
    if motec_ponto is not None and not motec_ponto.empty:
        df = _left_merge_on_fuel_keys(df, motec_ponto, extra_on=["Load_kW"])

    # --- 2. KiBox cleanup ---
    kibox_bug_cols = ["KIBOX_MBF_10_90_1", "KIBOX_MBF_10_90_AVG_1"]
    drop_now = [c for c in kibox_bug_cols if c in df.columns]
    if drop_now:
        df = df.drop(columns=drop_now)

    ai90_col = _find_kibox_col_by_tokens(df, ["ai", "90"])
    ai10_col = _find_kibox_col_by_tokens(df, ["ai", "10"])
    if ai90_col and ai10_col:
        df["MFB_10_90"] = pd.to_numeric(df[ai90_col], errors="coerce") - pd.to_numeric(df[ai10_col], errors="coerce")
    else:
        df["MFB_10_90"] = pd.NA
        if not ai90_col or not ai10_col:
            print(f"[WARN] Nao calculei MFB_10_90: ai90_col={ai90_col}, ai10_col={ai10_col}")

    # --- 3. Uncertainties from instruments ---
    N = pd.to_numeric(df["N_trechos_validos"], errors="coerce")
    df = add_uncertainties_from_mappings(
        df, mappings=mappings, instruments_df=instruments_df, N=N, defaults_cfg=defaults,
    )

    if "uB_Consumo_kg_h" in df.columns:
        df["uB_Consumo_kg_h_instrument"] = df["uB_Consumo_kg_h"]
    else:
        df["uB_Consumo_kg_h_instrument"] = pd.NA
    df["uB_Consumo_kg_h"] = pd.to_numeric(df.get("uB_Consumo_kg_h_mean_of_windows", pd.NA), errors="coerce")

    if "uA_Consumo_kg_h" in df.columns:
        df["uc_Consumo_kg_h"] = (pd.to_numeric(df["uA_Consumo_kg_h"], errors="coerce") ** 2 + pd.to_numeric(df["uB_Consumo_kg_h"], errors="coerce") ** 2) ** 0.5
        df["U_Consumo_kg_h"] = K_COVERAGE * df["uc_Consumo_kg_h"]
    else:
        df["uc_Consumo_kg_h"] = pd.NA
        df["U_Consumo_kg_h"] = pd.NA

    # --- 4. Fuel defaults ---
    merged_fuel_label = df.get("Fuel_Label", pd.Series(pd.NA, index=df.index, dtype="object"))
    fallback_fuel_label = _fuel_blend_labels(df)
    df["Fuel_Label"] = merged_fuel_label.where(merged_fuel_label.notna(), fallback_fuel_label)

    default_density, _missing_density_defaults = _fuel_default_lookup_series(df, defaults, field="density_param")
    merged_density = pd.to_numeric(df.get("Fuel_Density_kg_m3", pd.Series(pd.NA, index=df.index)), errors="coerce")
    df["Fuel_Density_kg_m3"] = merged_density.where(merged_density.gt(0), default_density)

    default_cost, _missing_cost_defaults = _fuel_default_lookup_series(df, defaults, field="cost_param")
    merged_cost = pd.to_numeric(df.get("Fuel_Cost_R_L", pd.Series(pd.NA, index=df.index)), errors="coerce")
    df["Fuel_Cost_R_L"] = merged_cost.where(merged_cost.gt(0), default_cost)

    missing_density = sorted({
        str(label) for label in df.loc[
            pd.to_numeric(df["Fuel_Density_kg_m3"], errors="coerce").le(0) | pd.to_numeric(df["Fuel_Density_kg_m3"], errors="coerce").isna(),
            "Fuel_Label",
        ].dropna() if str(label).strip()
    })
    missing_cost = sorted({
        str(label) for label in df.loc[
            pd.to_numeric(df["Fuel_Cost_R_L"], errors="coerce").le(0) | pd.to_numeric(df["Fuel_Cost_R_L"], errors="coerce").isna(),
            "Fuel_Label",
        ].dropna() if str(label).strip()
    })
    if missing_density:
        print("[WARN] Densidade ausente/invalida em Fuel Properties/Defaults para: " + ", ".join(sorted(set(missing_density))) + ". Consumo_L_h ficara vazio nesses combustiveis.")
    if missing_cost:
        print("[WARN] Custo por litro ausente/invalido em Fuel Properties/Defaults para: " + ", ".join(sorted(set(missing_cost))) + ". Custo_R_h ficara vazio nesses combustiveis.")

    # --- 5. Core derived quantities ---
    P_mean = resolve_col(df, mappings["power_kw"]["mean"])
    F_mean = resolve_col(df, mappings["fuel_kgh"]["mean"])
    L_col = resolve_col(df, mappings["lhv_kj_kg"]["mean"])

    PkW = pd.to_numeric(df[P_mean], errors="coerce")
    Fkgh = pd.to_numeric(df[F_mean], errors="coerce")
    fuel_density = pd.to_numeric(df["Fuel_Density_kg_m3"], errors="coerce")
    fuel_cost = pd.to_numeric(df["Fuel_Cost_R_L"], errors="coerce")
    mdot = Fkgh / 3600.0
    LHVv = pd.to_numeric(df[L_col], errors="coerce")
    lhv_e94h6_kj_kg = _lookup_lhv_for_blend(fuel_properties, etoh_pct=94.0, h2o_pct=6.0)

    df["UPD_Power_kW"] = PkW
    df["UPD_Power_Bin_kW"] = PkW.round(1).where(PkW.notna(), pd.NA)
    df["LHV_E94H6_kJ_kg"] = lhv_e94h6_kj_kg if np.isfinite(lhv_e94h6_kj_kg) else pd.NA
    if not np.isfinite(lhv_e94h6_kj_kg):
        print("[WARN] LHV E94H6 (94/6) nao encontrado em Fuel Properties; n_th_E94H6_eq_flow ficara vazio.")

    # --- 5a. Thermal efficiency ---
    df["n_th"] = PkW / (mdot * LHVv)
    df.loc[(PkW <= 0) | (mdot <= 0) | (LHVv <= 0), "n_th"] = pd.NA
    df["n_th_pct"] = df["n_th"] * 100.0

    ucP = pd.to_numeric(df.get("uc_P_kw", pd.NA), errors="coerce")
    ucF = pd.to_numeric(df.get("uc_Consumo_kg_h", pd.NA), errors="coerce")
    uBL = pd.to_numeric(df.get("uB_LHV_kJ_kg", pd.NA), errors="coerce")
    rel_uc = ((ucP / PkW) ** 2 + (ucF / Fkgh) ** 2 + (uBL / LHVv) ** 2) ** 0.5
    df["uc_n_th"] = df["n_th"] * rel_uc
    df["U_n_th"] = K_COVERAGE * df["uc_n_th"]
    df["uc_n_th_pct"] = df["uc_n_th"] * 100.0
    df["U_n_th_pct"] = df["U_n_th"] * 100.0

    # --- 5b. Consumo L/h ---
    volume_factor = 1000.0 / fuel_density
    valid_volumetric = Fkgh.notna() & fuel_density.gt(0)
    df["Consumo_L_h"] = (Fkgh * volume_factor).where(valid_volumetric, pd.NA)
    for src_col, dst_col in [
        ("uA_Consumo_kg_h", "uA_Consumo_L_h"),
        ("uB_Consumo_kg_h", "uB_Consumo_L_h"),
        ("uc_Consumo_kg_h", "uc_Consumo_L_h"),
        ("U_Consumo_kg_h", "U_Consumo_L_h"),
    ]:
        src = pd.to_numeric(df.get(src_col, pd.NA), errors="coerce")
        df[dst_col] = (src * volume_factor).where(valid_volumetric, pd.NA)

    # --- 5c. Custo R/h ---
    consumo_l_h = pd.to_numeric(df["Consumo_L_h"], errors="coerce")
    valid_cost = consumo_l_h.notna() & fuel_cost.gt(0)
    df["Custo_R_h"] = (consumo_l_h * fuel_cost).where(valid_cost, pd.NA)
    for src_col, dst_col in [
        ("uA_Consumo_L_h", "uA_Custo_R_h"),
        ("uB_Consumo_L_h", "uB_Custo_R_h"),
        ("uc_Consumo_L_h", "uc_Custo_R_h"),
        ("U_Consumo_L_h", "U_Custo_R_h"),
    ]:
        src = pd.to_numeric(df.get(src_col, pd.NA), errors="coerce")
        df[dst_col] = (src * fuel_cost).where(valid_cost, pd.NA)

    # --- 5d. Diesel cost delta + machine scenarios ---
    df = _attach_diesel_cost_delta_metrics(df)
    df = _attach_e94h6_machine_scenario_metrics(df, defaults)

    # --- 5e. BSFC ---
    bsfc = (Fkgh * 1000.0) / PkW
    invalid_bsfc = (PkW <= 0) | (Fkgh <= 0)
    df["BSFC_g_kWh"] = bsfc.where(~invalid_bsfc, pd.NA)

    uA_P = pd.to_numeric(df.get("uA_P_kw", pd.NA), errors="coerce")
    uB_P = pd.to_numeric(df.get("uB_P_kw", pd.NA), errors="coerce")
    uA_F = pd.to_numeric(df.get("uA_Consumo_kg_h", pd.NA), errors="coerce")
    uB_F = pd.to_numeric(df.get("uB_Consumo_kg_h", pd.NA), errors="coerce")
    rel_uA_bsfc = ((uA_F / Fkgh) ** 2 + (uA_P / PkW) ** 2) ** 0.5
    rel_uB_bsfc = ((uB_F / Fkgh) ** 2 + (uB_P / PkW) ** 2) ** 0.5
    df["uA_BSFC_g_kWh"] = pd.to_numeric(df["BSFC_g_kWh"], errors="coerce") * rel_uA_bsfc
    df["uB_BSFC_g_kWh"] = pd.to_numeric(df["BSFC_g_kWh"], errors="coerce") * rel_uB_bsfc
    ua_bsfc = pd.to_numeric(df["uA_BSFC_g_kWh"], errors="coerce")
    ub_bsfc = pd.to_numeric(df["uB_BSFC_g_kWh"], errors="coerce")
    df["uc_BSFC_g_kWh"] = (ua_bsfc**2 + ub_bsfc**2) ** 0.5
    df["U_BSFC_g_kWh"] = K_COVERAGE * df["uc_BSFC_g_kWh"]
    df.loc[invalid_bsfc, ["uA_BSFC_g_kWh", "uB_BSFC_g_kWh", "uc_BSFC_g_kWh", "U_BSFC_g_kWh"]] = pd.NA

    # --- 5f. Delta vs reference fuel ---
    df = _attach_delta_vs_ref_metrics(df)

    # --- 6. Airflow ---
    lambda_col = _resolve_airflow_lambda_col(df, mappings)
    maf_col = _resolve_airflow_maf_col(df, defaults)
    maf_min_kgh = _to_float(defaults.get(norm_key("VOL_EFF_DIESEL_MAF_MIN_KGH"), ""), default=0.0)
    maf_max_kgh = _to_float(defaults.get(norm_key("VOL_EFF_DIESEL_MAF_MAX_KGH"), ""), default=300.0)

    if lambda_col:
        print(f"[INFO] Airflow: lambda da MoTeC = '{lambda_col}'.")
    else:
        print("[INFO] Airflow: lambda da MoTeC nao encontrada; vou priorizar MAF e usar lambda default=1.0 apenas no fallback fuel+lambda.")
    if maf_col:
        print(f"[INFO] Airflow: MAF = '{maf_col}' (faixa valida {maf_min_kgh:g}..{maf_max_kgh:g} kg/h).")
    else:
        print("[INFO] Airflow: MAF nao encontrado; airflow ficara no modo fuel+lambda.")

    df = add_airflow_channels_prefer_maf_inplace(
        df, lambda_col=lambda_col, maf_col=maf_col, maf_min_kgh=maf_min_kgh, maf_max_kgh=maf_max_kgh,
    )

    airflow_methods = df.get("Airflow_Method", pd.Series(pd.NA, index=df.index, dtype="object")).fillna("unavailable")
    airflow_counts = airflow_methods.value_counts(dropna=False)
    airflow_summary = ", ".join(
        f"{label}={int(count)}"
        for label, count in [
            ("MAF", airflow_counts.get("MAF", 0)),
            ("fuel+lambda", airflow_counts.get("fuel_lambda", 0)),
            ("fuel+lambda_default", airflow_counts.get("fuel_lambda_default", 0)),
            ("indisponivel", airflow_counts.get("unavailable", 0)),
        ]
        if int(count) > 0
    )
    lambda_source_counts = df.get("LAMBDA_SOURCE", pd.Series(pd.NA, index=df.index, dtype="object")).fillna("default_1.0").value_counts(dropna=False)
    print(
        "[INFO] Airflow por ponto: "
        + (airflow_summary if airflow_summary else "nenhum ponto valido")
        + f" | lambda medida={int(lambda_source_counts.get('measured', 0))}, default_1.0={int(lambda_source_counts.get('default_1.0', 0))}"
    )

    # --- 7. Emissions g/kWh ---
    df = add_specific_emissions_channels_inplace(df, power_kW=PkW, fuel_kg_h=Fkgh, defaults_cfg=defaults)

    humidity_source_counts = (
        df.get("EMISSIONS_H2O_SOURCE", pd.Series(pd.NA, index=df.index, dtype="object"))
        .fillna("indisponivel")
        .value_counts(dropna=False)
    )
    humidity_source_summary = ", ".join(f"{label}={int(count)}" for label, count in humidity_source_counts.items() if int(count) > 0)
    print(
        "[INFO] Emissoes g/kWh: H2O_wet_frac indireto via "
        + (humidity_source_summary if humidity_source_summary else "indisponivel")
        + " | agua no escape = agua do ar + agua no combustivel + agua formada pelo H do combustivel."
    )

    thc_low_mask = pd.to_numeric(df.get("THC_LOW_SIGNAL_FLAG", pd.NA), errors="coerce").fillna(0).gt(0)
    thc_neg_mask = pd.to_numeric(df.get("THC_NEGATIVE_FLAG", pd.NA), errors="coerce").fillna(0).gt(0)
    if bool(thc_low_mask.any()):
        print(f"[WARN] THC muito baixo em {int(thc_low_mask.sum())} ponto(s) (|THC| < {THC_LOW_SIGNAL_WARN_PPM:g} ppm); vou calcular e plotar THC_g_kWh mesmo assim.")
    if bool(thc_neg_mask.any()):
        print(f"[WARN] THC negativo em {int(thc_neg_mask.sum())} ponto(s); vou calcular e plotar THC_g_kWh mesmo assim para preservar o diagnostico do analisador.")

    # --- 8. Emission uncertainty propagation ---
    def _series_or_na(col_name: str) -> pd.Series:
        if col_name in df.columns:
            return pd.to_numeric(df[col_name], errors="coerce")
        return pd.Series(np.nan, index=df.index, dtype="float64")

    if "NOx_g_kWh" not in df.columns and "NOx_g_kWh_as_NO" in df.columns:
        df["NOx_g_kWh"] = pd.to_numeric(df["NOx_g_kWh_as_NO"], errors="coerce")

    emission_uncertainty_specs = [
        ("CO_g_kWh",  "CO_mean_of_windows",  "CO_pct"),
        ("CO2_g_kWh", "CO2_mean_of_windows", "CO2_pct"),
        ("NOx_g_kWh", "NOX_mean_of_windows", "NOx_ppm"),
        ("THC_g_kWh", "THC_mean_of_windows", "THC_ppm"),
    ]
    for value_col, conc_col, conc_prefix in emission_uncertainty_specs:
        value = _series_or_na(value_col)
        conc = _series_or_na(conc_col)
        uA_conc = _series_or_na(f"uA_{conc_prefix}")
        uB_conc = _series_or_na(f"uB_{conc_prefix}")
        safe_conc = conc.where(conc.abs().gt(0), pd.NA)
        safe_P = PkW.where(PkW.gt(0), pd.NA)
        safe_F = Fkgh.where(Fkgh.gt(0), pd.NA)
        rel_uA = ((uA_conc / safe_conc) ** 2 + (uA_P / safe_P) ** 2 + (uA_F / safe_F) ** 2) ** 0.5
        rel_uB = ((uB_conc / safe_conc) ** 2 + (uB_P / safe_P) ** 2 + (uB_F / safe_F) ** 2) ** 0.5
        abs_value = value.abs()
        uA_value = abs_value * rel_uA
        uB_value = abs_value * rel_uB
        uc_value = (uA_value ** 2 + uB_value ** 2) ** 0.5
        U_value = K_COVERAGE * uc_value
        valid = value.notna()
        df[f"uA_{value_col}"] = uA_value.where(valid, pd.NA)
        df[f"uB_{value_col}"] = uB_value.where(valid, pd.NA)
        df[f"uc_{value_col}"] = uc_value.where(valid, pd.NA)
        df[f"U_{value_col}"] = U_value.where(valid, pd.NA)

    for nox_variant in ("NOx_g_kWh_as_NO", "NOx_g_kWh_as_NO2", "NOx_as_NO_g_kWh", "NOx_as_NO2_g_kWh"):
        if nox_variant not in df.columns:
            continue
        base_value = _series_or_na(nox_variant)
        base_nox = _series_or_na("NOx_g_kWh")
        ratio = (base_value / base_nox).where(base_nox.abs().gt(0), pd.NA)
        for suffix in ("uA", "uB", "uc", "U"):
            src = _series_or_na(f"{suffix}_NOx_g_kWh")
            df[f"{suffix}_{nox_variant}"] = (src * ratio).where(base_value.notna(), pd.NA)

    # --- 9. E94H6 equivalent flow thermal efficiency ---
    F_eq_kgh = pd.to_numeric(df.get("Fuel_E94H6_eq_kg_h", pd.NA), errors="coerce")
    mdot_eq = F_eq_kgh / 3600.0
    lhv_e94_series = pd.to_numeric(df.get("LHV_E94H6_kJ_kg", pd.NA), errors="coerce")
    qdot_mix_lhv = mdot * LHVv
    qdot_eq_e94 = mdot_eq * lhv_e94_series

    df["Qdot_fuel_LHV_mix_kW"] = qdot_mix_lhv
    df["Qdot_fuel_E94H6_eq_kW"] = qdot_eq_e94
    df["n_th_E94H6_eq_flow"] = PkW / qdot_eq_e94
    df.loc[(PkW <= 0) | (mdot_eq <= 0) | (lhv_e94_series <= 0), "n_th_E94H6_eq_flow"] = pd.NA
    df["n_th_E94H6_eq_flow_pct"] = df["n_th_E94H6_eq_flow"] * 100.0

    # --- 10. Temperature ---
    t_cil_cols = [
        "T_S_CIL_1_mean_of_windows", "T_S_CIL_2_mean_of_windows",
        "T_S_CIL_3_mean_of_windows", "T_S_CIL_4_mean_of_windows",
    ]
    df = _combine_average_temperature_uncertainties(
        df, mean_cols=t_cil_cols,
        source_prefixes=["T_S_CIL_1_C", "T_S_CIL_2_C", "T_S_CIL_3_C", "T_S_CIL_4_C"],
        target_mean_col="T_E_CIL_AVG_mean_of_windows",
        target_prefix="T_E_CIL_AVG_C",
    )

    t_e_comp_col = _resolve_existing_column(df, "T_E_COMP_mean_of_windows", ["t_e_comp"])
    t_adm_col = _find_first_col_by_substrings(df, ["t", "admiss"])
    p_col = _find_first_col_by_substrings(df, ["p", "coletor"])
    rh_col = _find_first_col_by_substrings(df, ["umidade"])

    if t_e_comp_col and rh_col:
        df["UMIDADE_ABS_g_m3"] = _absolute_humidity_g_m3(df[t_e_comp_col], df[rh_col])
    else:
        df["UMIDADE_ABS_g_m3"] = pd.NA

    if t_adm_col and rh_col and p_col:
        df["cp_air_dry_kJ_kgK"] = _cp_air_dry_kj_kgk(df[t_adm_col])
        df["cp_air_moist_kJ_kgK"] = _cp_moist_air_kj_kgk(df[t_adm_col], df[rh_col], df[p_col])
        df["hum_ratio_w_kgkg"] = _humidity_ratio_w_from_rh(df[t_adm_col], df[rh_col], df[p_col])
    else:
        df["cp_air_dry_kJ_kgK"] = pd.NA
        df["cp_air_moist_kJ_kgK"] = pd.NA
        df["hum_ratio_w_kgkg"] = pd.NA

    if t_adm_col and "T_E_CIL_AVG_mean_of_windows" in df.columns:
        df = _combine_delta_temperature_uncertainties(
            df,
            minuend_col="T_E_CIL_AVG_mean_of_windows", subtrahend_col=t_adm_col,
            minuend_prefix="T_E_CIL_AVG_C", subtrahend_prefix="T_ADMISSAO_C",
            target_value_col="DT_ADMISSAO_TO_T_E_CIL_AVG_C",
            target_prefix="DT_ADMISSAO_TO_T_E_CIL_AVG_C",
        )
    else:
        df["DT_ADMISSAO_TO_T_E_CIL_AVG_C"] = pd.NA
        for suffix in ("uA", "uB", "uc", "U"):
            df[f"{suffix}_DT_ADMISSAO_TO_T_E_CIL_AVG_C"] = pd.NA

    if "Air_kg_h" in df.columns and t_adm_col and "T_E_CIL_AVG_mean_of_windows" in df.columns:
        mdot_air = pd.to_numeric(df["Air_kg_h"], errors="coerce") / 3600.0
        dT = pd.to_numeric(df["DT_ADMISSAO_TO_T_E_CIL_AVG_C"], errors="coerce")
        cp_used = pd.to_numeric(df["cp_air_moist_kJ_kgK"], errors="coerce")
        cp_fallback = pd.to_numeric(df["cp_air_dry_kJ_kgK"], errors="coerce")
        cp_used = cp_used.where(cp_used.notna(), cp_fallback)
        cp_used = cp_used.where(cp_used.notna(), 1.005)
        df["Q_EVAP_NET_kW"] = mdot_air * cp_used * dT
    else:
        df["Q_EVAP_NET_kW"] = pd.NA

    # --- 11. Volumetric efficiency ---
    df = add_volumetric_efficiency_from_airflow_method_inplace(df, defaults)

    # --- 12. ECT control error ---
    t_s_agua_col = None
    for cand in ["T_S_AGUA_mean_of_windows", "T_S_AGUA", "T_S_ÁGUA"]:
        if cand in df.columns:
            t_s_agua_col = cand
            break
    if t_s_agua_col is None:
        t_s_agua_col = _find_first_col_by_substrings(df, ["t_s", "agua", "mean_of_windows"])
    if t_s_agua_col is None:
        t_s_agua_col = _find_first_col_by_substrings(df, ["t_s", "agua"])
    if t_s_agua_col is None:
        t_s_agua_col = _find_first_col_by_substrings(df, ["t_s", "água"])

    dem_th2o_col = None
    for cand in ["DEM_TH2O_mean_of_windows", "DEM TH2O_mean_of_windows", "DEM_TH2O", "DEM TH2O"]:
        if cand in df.columns:
            dem_th2o_col = cand
            break
    if dem_th2o_col is None:
        dem_th2o_col = _find_first_col_by_substrings(df, ["dem", "th2o", "mean_of_windows"])
    if dem_th2o_col is None:
        dem_th2o_col = _find_first_col_by_substrings(df, ["dem", "th2o"])

    if t_s_agua_col and dem_th2o_col:
        ect_actual = pd.to_numeric(df[t_s_agua_col], errors="coerce")
        ect_target = pd.to_numeric(df[dem_th2o_col], errors="coerce")
        df["ECT_CTRL_ACTUAL_C"] = ect_actual
        df["ECT_CTRL_TARGET_C"] = ect_target
        df["ECT_CTRL_ERROR_C"] = ect_actual - ect_target
        df["ECT_CTRL_ERROR_ABS_C"] = pd.to_numeric(df["ECT_CTRL_ERROR_C"], errors="coerce").abs()
    else:
        df["ECT_CTRL_ACTUAL_C"] = pd.NA
        df["ECT_CTRL_TARGET_C"] = pd.NA
        df["ECT_CTRL_ERROR_C"] = pd.NA
        df["ECT_CTRL_ERROR_ABS_C"] = pd.NA

    # --- 13. Ignition delay ---
    motec_ign_col = "Motec_Ignition Timing_mean_of_windows"
    kibox_ai05_col = "KIBOX_AI05_1"
    motec_ign = pd.to_numeric(
        df.get(motec_ign_col, pd.Series(pd.NA, index=df.index, dtype="Float64")), errors="coerce",
    )
    kibox_ai05 = pd.to_numeric(
        df.get(kibox_ai05_col, pd.Series(pd.NA, index=df.index, dtype="Float64")), errors="coerce",
    )
    delay_abs = (kibox_ai05 + motec_ign).abs()
    df["Ignition_Delay_abs_degCA"] = delay_abs.where(motec_ign.notna() & kibox_ai05.notna(), pd.NA)

    # --- 14. Run context + reporting ---
    df = add_run_context_columns(df)
    df = _apply_reporting_rounding(df, mappings=mappings, reporting_df=reporting_df)

    first_cols = [c for c in ["Iteracao", "Sentido_Carga"] if c in df.columns]
    if first_cols:
        rest_cols = [c for c in df.columns if c not in first_cols]
        df = df[first_cols + rest_cols].copy()

    return df
