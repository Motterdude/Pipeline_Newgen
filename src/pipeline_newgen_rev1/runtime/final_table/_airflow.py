"""Airflow channels: MAF vs fuel+lambda, stoichiometric blend computation."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pandas as pd

from ._fuel_defaults import _fuel_blend_labels
from ._helpers import (
    _find_preferred_column,
    _nan_series,
    _to_float,
    _to_str_or_empty,
    norm_key,
    resolve_col,
)
from .constants import (
    AFR_STOICH_BIODIESEL,
    AFR_STOICH_DIESEL,
    AFR_STOICH_E94H6,
    AFR_STOICH_ETHANOL,
    ETHANOL_FRAC_E94H6,
    LAMBDA_DEFAULT,
)


def _ethanol_mass_fraction_from_etoh_pct(etoh_pct: pd.Series) -> pd.Series:
    return pd.to_numeric(etoh_pct, errors="coerce") / 100.0


def _airflow_component_fraction(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df.get(column, _nan_series(df.index)), errors="coerce") / 100.0


def _ethanol_trial_mask(df: pd.DataFrame) -> pd.Series:
    etoh = pd.to_numeric(df.get("EtOH_pct", _nan_series(df.index)), errors="coerce")
    h2o = pd.to_numeric(df.get("H2O_pct", _nan_series(df.index)), errors="coerce")
    return etoh.gt(0) | h2o.gt(0)


def _diesel_like_no_ethanol_mask(df: pd.DataFrame) -> pd.Series:
    dies = pd.to_numeric(df.get("DIES_pct", _nan_series(df.index)), errors="coerce")
    biod = pd.to_numeric(df.get("BIOD_pct", _nan_series(df.index)), errors="coerce")
    return (dies.gt(0) | biod.gt(0)) & ~_ethanol_trial_mask(df)


def _airflow_stoich_blend_from_composition(df: pd.DataFrame) -> pd.Series:
    dies_frac = _airflow_component_fraction(df, "DIES_pct")
    biod_frac = _airflow_component_fraction(df, "BIOD_pct")
    etoh_frac = _airflow_component_fraction(df, "EtOH_pct")
    valid_components = dies_frac.notna() | biod_frac.notna() | etoh_frac.notna()
    blend_afr = (
        dies_frac.fillna(0.0) * AFR_STOICH_DIESEL
        + biod_frac.fillna(0.0) * AFR_STOICH_BIODIESEL
        + etoh_frac.fillna(0.0) * AFR_STOICH_ETHANOL
    )
    return blend_afr.where(valid_components & blend_afr.gt(0), pd.NA)


def _series_is_static(values: pd.Series, tol: float = 1e-9) -> bool:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return False
    if numeric.nunique(dropna=True) <= 1:
        return True
    try:
        return float(numeric.max() - numeric.min()) <= tol
    except Exception:
        return False


def _static_maf_mask_by_fuel(maf: pd.Series, fuel_labels: pd.Series, *, min_points: int = 4) -> Tuple[pd.Series, List[str]]:
    invalid_mask = pd.Series(False, index=maf.index, dtype="bool")
    static_labels: List[str] = []
    labels = fuel_labels.map(_to_str_or_empty).replace("", pd.NA)
    for label in sorted(v for v in labels.dropna().unique().tolist() if _to_str_or_empty(v)):
        label_mask = labels.eq(label)
        label_maf = pd.to_numeric(maf.where(label_mask), errors="coerce").dropna()
        if len(label_maf) < min_points:
            continue
        if _series_is_static(label_maf):
            invalid_mask = invalid_mask | (label_mask & maf.notna())
            static_labels.append(str(label))
    return invalid_mask, static_labels


def _resolve_airflow_lambda_col(df: pd.DataFrame, mappings: dict) -> Optional[str]:
    preferred_names: List[str] = []
    if "lambda" in mappings and mappings["lambda"].get("mean"):
        preferred_names.append(mappings["lambda"]["mean"])
    preferred_names.extend([
        "Motec_Exhaust Lambda_mean_of_windows",
        "Exhaust Lambda_mean_of_windows",
        "Lambda_mean_of_windows",
    ])
    return _find_preferred_column(
        df, preferred_names=preferred_names,
        include_tokens=["lambda", "mean"],
        exclude_tokens=["sd", "diagnostic", "normalised", "normalized"],
    )


def _resolve_airflow_maf_col(df: pd.DataFrame, defaults_cfg: Dict[str, str]) -> Optional[str]:
    preferred_name = _to_str_or_empty(defaults_cfg.get(norm_key("VOL_EFF_DIESEL_MAF_COL"), "")) or "MAF_mean_of_windows"
    return _find_preferred_column(
        df, preferred_names=[preferred_name, "MAF_mean_of_windows", "Motec_MAF_mean_of_windows"],
        include_tokens=["maf"], exclude_tokens=["sd"],
    )


def add_airflow_channels_prefer_maf_inplace(
    df: pd.DataFrame,
    lambda_col: Optional[str] = None,
    maf_col: Optional[str] = None,
    *,
    maf_min_kgh: float = 0.0,
    maf_max_kgh: float = 300.0,
) -> pd.DataFrame:
    out = df.copy()
    nan_s = _nan_series(out.index)

    fuel_col = None
    for c in ["Consumo_kg_h_mean_of_windows", "Consumo_kg_h", "Fuel_kg_h", "fuel_kgh_mean_of_windows"]:
        if c in out.columns:
            fuel_col = c
            break
    if fuel_col is None and not out.empty:
        candidates = [c for c in out.columns if "consumo" in c.lower() and "mean_of_windows" in c.lower()]
        fuel_col = candidates[0] if candidates else None

    fuel_mix_kg_h = pd.to_numeric(out[fuel_col], errors="coerce") if fuel_col else nan_s.copy()

    x_etoh = _ethanol_mass_fraction_from_etoh_pct(out.get("EtOH_pct", nan_s))
    out["EtOH_pure_mass_frac"] = x_etoh
    out["Fuel_EtOH_pure_kg_h"] = fuel_mix_kg_h * x_etoh
    out["Fuel_E94H6_eq_kg_h"] = out["Fuel_EtOH_pure_kg_h"] / ETHANOL_FRAC_E94H6

    lambda_measured = pd.to_numeric(out[lambda_col], errors="coerce") if lambda_col and lambda_col in out.columns else nan_s.copy()
    lambda_valid = lambda_measured.gt(0)
    out["lambda_used"] = lambda_measured.where(lambda_valid, LAMBDA_DEFAULT)
    out["LAMBDA_SOURCE"] = pd.Series("default_1.0", index=out.index, dtype="object")
    out.loc[lambda_valid, "LAMBDA_SOURCE"] = "measured"

    out["AFR_stoich_blend"] = _airflow_stoich_blend_from_composition(out)
    out["AFR_stoich_E94H6"] = AFR_STOICH_E94H6
    out["AFR_real"] = out["lambda_used"] * out["AFR_stoich_blend"]

    out["Air_kg_h_from_Fuel_Lambda"] = (
        pd.to_numeric(out["AFR_real"], errors="coerce") * fuel_mix_kg_h
    ).where(fuel_mix_kg_h.gt(0) & pd.to_numeric(out["AFR_real"], errors="coerce").gt(0), pd.NA)

    maf = pd.to_numeric(out[maf_col], errors="coerce") if maf_col and maf_col in out.columns else nan_s.copy()
    fuel_labels = out.get("Fuel_Label", pd.Series(pd.NA, index=out.index, dtype="object"))
    fuel_labels = fuel_labels.where(fuel_labels.notna(), _fuel_blend_labels(out))
    ethanol_mask = _ethanol_trial_mask(out)
    diesel_like_mask = _diesel_like_no_ethanol_mask(out)

    ignored_ethanol_maf_mask = ethanol_mask & maf.notna()
    if bool(ignored_ethanol_maf_mask.any()):
        ignored_labels = sorted({
            str(label).strip()
            for label in fuel_labels.where(ignored_ethanol_maf_mask).dropna().tolist()
            if str(label).strip()
        })
        ignored_txt = ", ".join(ignored_labels) if ignored_labels else "combustiveis com etanol"
        print(
            f"[INFO] Airflow: MAF ignorado em {int(ignored_ethanol_maf_mask.sum())} ponto(s) com etanol "
            f"({ignored_txt}); vou usar consumo+lambda por regra."
        )

    static_maf_mask, static_maf_labels = _static_maf_mask_by_fuel(maf.where(diesel_like_mask), fuel_labels.where(diesel_like_mask))
    if static_maf_labels:
        print(f"[WARN] Airflow: ignorei MAF estatico para {', '.join(static_maf_labels)}. Vou usar fuel+lambda nesses combustiveis.")
    maf_valid = diesel_like_mask & maf.gt(0) & maf.between(maf_min_kgh, maf_max_kgh, inclusive="both") & ~static_maf_mask
    invalid_maf_mask = diesel_like_mask & maf.notna() & ~maf_valid & ~static_maf_mask
    if bool(invalid_maf_mask.any()):
        print(
            f"[WARN] Airflow: {int(invalid_maf_mask.sum())} ponto(s) com MAF fora de {maf_min_kgh:g}..{maf_max_kgh:g} kg/h; "
            "vou usar fuel+lambda nesses pontos."
        )
    out["Air_kg_h_from_MAF"] = maf.where(maf_valid, pd.NA)

    out["Air_kg_h"] = out["Air_kg_h_from_MAF"].where(out["Air_kg_h_from_MAF"].notna(), out["Air_kg_h_from_Fuel_Lambda"])
    out["Air_kg_s"] = out["Air_kg_h"] / 3600.0
    out["Air_g_s"] = out["Air_kg_s"] * 1000.0

    out["Airflow_Method"] = pd.Series("unavailable", index=out.index, dtype="object")
    out.loc[out["Air_kg_h_from_MAF"].notna(), "Airflow_Method"] = "MAF"
    fuel_lambda_mask = out["Air_kg_h_from_MAF"].isna() & out["Air_kg_h_from_Fuel_Lambda"].notna()
    out.loc[fuel_lambda_mask & out["LAMBDA_SOURCE"].eq("measured"), "Airflow_Method"] = "fuel_lambda"
    out.loc[fuel_lambda_mask & out["LAMBDA_SOURCE"].ne("measured"), "Airflow_Method"] = "fuel_lambda_default"

    if fuel_col is None and not bool(maf_valid.any()):
        print("[WARN] Airflow: nao achei consumo em kg/h nem MAF valido. Canais de ar ficaram vazios.")

    return out
