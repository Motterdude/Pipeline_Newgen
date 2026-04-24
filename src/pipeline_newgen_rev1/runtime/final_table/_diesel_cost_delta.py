"""Economy vs D85B15 diesel baseline metrics."""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from ._fuel_defaults import _fuel_blend_labels
from ._helpers import _nan_series
from .constants import K_COVERAGE


def _rss_or_na(values: pd.Series) -> float:
    v = pd.to_numeric(values, errors="coerce").dropna()
    if v.empty:
        return float("nan")
    return float(np.sqrt(np.sum(np.square(v.to_numpy(dtype=float)))))


def _aggregate_metric_with_uncertainty(
    df: pd.DataFrame,
    *,
    group_cols: List[str],
    value_col: str,
    uA_col: str,
    uB_col: str,
    uc_col: str,
    U_col: str,
    value_name: str,
) -> pd.DataFrame:
    out_cols = group_cols + [
        value_name, f"uA_{value_name}", f"uB_{value_name}",
        f"uc_{value_name}", f"U_{value_name}", "n_points",
    ]
    if df is None or df.empty:
        return pd.DataFrame(columns=out_cols)
    tmp = df.copy()
    required_cols = group_cols + [value_col, uA_col, uB_col, uc_col, U_col]
    for c in required_cols:
        if c not in tmp.columns:
            tmp[c] = pd.NA
    tmp = tmp.dropna(subset=group_cols).copy()
    for c in [value_col, uA_col, uB_col, uc_col, U_col]:
        tmp[c] = pd.to_numeric(tmp[c], errors="coerce")
    tmp = tmp.dropna(subset=[value_col]).copy()
    if tmp.empty:
        return pd.DataFrame(columns=out_cols)
    g = (
        tmp.groupby(group_cols, dropna=False, sort=True)
        .agg(**{
            value_name: (value_col, "mean"),
            "n_points": (value_col, "count"),
            "_uA_rss": (uA_col, _rss_or_na),
            "_uB_rss": (uB_col, _rss_or_na),
            "_uc_rss": (uc_col, _rss_or_na),
            "_U_rss": (U_col, _rss_or_na),
        })
        .reset_index()
    )
    n = pd.to_numeric(g["n_points"], errors="coerce").replace(0, np.nan)
    g[f"uA_{value_name}"] = g["_uA_rss"] / n
    g[f"uB_{value_name}"] = g["_uB_rss"] / n
    g[f"uc_{value_name}"] = (
        pd.to_numeric(g[f"uA_{value_name}"], errors="coerce") ** 2
        + pd.to_numeric(g[f"uB_{value_name}"], errors="coerce") ** 2
    ) ** 0.5
    g[f"uc_{value_name}"] = g[f"uc_{value_name}"].where(
        g[f"uc_{value_name}"].notna(), g["_uc_rss"] / n,
    )
    g[f"U_{value_name}"] = K_COVERAGE * pd.to_numeric(g[f"uc_{value_name}"], errors="coerce")
    g[f"U_{value_name}"] = g[f"U_{value_name}"].where(
        g[f"U_{value_name}"].notna(), g["_U_rss"] / n,
    )
    return g[out_cols].copy()


def _attach_diesel_cost_delta_metrics(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    idx = out.index
    fuel_labels = out.get("Fuel_Label", pd.Series(pd.NA, index=idx, dtype="object"))
    fuel_labels = fuel_labels.where(fuel_labels.notna(), _fuel_blend_labels(out))
    out["Fuel_Label"] = fuel_labels

    load_key = pd.to_numeric(out.get("Load_kW", pd.Series(pd.NA, index=idx)), errors="coerce").round(6)
    out["_diesel_baseline_load_key"] = load_key

    diesel_points = out[fuel_labels.eq("D85B15")].copy()
    diesel_points = diesel_points[diesel_points["_diesel_baseline_load_key"].notna()].copy()

    baseline_ref_cols = [
        "Diesel_Baseline_Custo_R_h", "uA_Diesel_Baseline_Custo_R_h",
        "uB_Diesel_Baseline_Custo_R_h", "uc_Diesel_Baseline_Custo_R_h",
        "U_Diesel_Baseline_Custo_R_h", "Diesel_Baseline_N_points",
    ]
    delta_cols = [
        "Razao_Custo_vs_Diesel", "Economia_vs_Diesel_R_h",
        "uA_Economia_vs_Diesel_R_h", "uB_Economia_vs_Diesel_R_h",
        "uc_Economia_vs_Diesel_R_h", "U_Economia_vs_Diesel_R_h",
        "Economia_vs_Diesel_pct",
        "uA_Economia_vs_Diesel_pct", "uB_Economia_vs_Diesel_pct",
        "uc_Economia_vs_Diesel_pct", "U_Economia_vs_Diesel_pct",
        "delta_over_U_Economia_vs_Diesel_pct", "Interpretacao_Economia_vs_Diesel",
    ]
    for c in delta_cols:
        if c not in out.columns:
            out[c] = pd.NA

    if diesel_points.empty:
        print("[WARN] Nao encontrei pontos Diesel D85B15 para calcular economia vs diesel.")
        for c in baseline_ref_cols:
            if c not in out.columns:
                out[c] = pd.NA
        return out.drop(columns=["_diesel_baseline_load_key"], errors="ignore")

    diesel_baseline = _aggregate_metric_with_uncertainty(
        diesel_points, group_cols=["_diesel_baseline_load_key"],
        value_col="Custo_R_h", uA_col="uA_Custo_R_h", uB_col="uB_Custo_R_h",
        uc_col="uc_Custo_R_h", U_col="U_Custo_R_h",
        value_name="Diesel_Baseline_Custo_R_h",
    )
    if diesel_baseline.empty:
        print("[WARN] Nao consegui agregar o baseline Diesel por carga para economia vs diesel.")
        for c in baseline_ref_cols:
            if c not in out.columns:
                out[c] = pd.NA
        return out.drop(columns=["_diesel_baseline_load_key"], errors="ignore")

    diesel_baseline = diesel_baseline.rename(columns={"n_points": "Diesel_Baseline_N_points"})
    out = out.drop(columns=baseline_ref_cols, errors="ignore")
    out = out.merge(diesel_baseline, on="_diesel_baseline_load_key", how="left", suffixes=("", "_drop"))
    out = out.drop(columns=[c for c in out.columns if c.endswith("_drop")], errors="ignore")

    custo_atual = pd.to_numeric(out.get("Custo_R_h", pd.NA), errors="coerce")
    custo_diesel = pd.to_numeric(out.get("Diesel_Baseline_Custo_R_h", pd.NA), errors="coerce")
    valid_delta = custo_atual.notna() & custo_diesel.gt(0)

    ua_atual = pd.to_numeric(out.get("uA_Custo_R_h", pd.NA), errors="coerce")
    ub_atual = pd.to_numeric(out.get("uB_Custo_R_h", pd.NA), errors="coerce")
    uc_atual = pd.to_numeric(out.get("uc_Custo_R_h", pd.NA), errors="coerce")
    ua_diesel = pd.to_numeric(out.get("uA_Diesel_Baseline_Custo_R_h", pd.NA), errors="coerce")
    ub_diesel = pd.to_numeric(out.get("uB_Diesel_Baseline_Custo_R_h", pd.NA), errors="coerce")
    uc_diesel = pd.to_numeric(out.get("uc_Diesel_Baseline_Custo_R_h", pd.NA), errors="coerce")

    out["Razao_Custo_vs_Diesel"] = (custo_atual / custo_diesel).where(valid_delta, pd.NA)
    out["Economia_vs_Diesel_R_h"] = (custo_atual - custo_diesel).where(valid_delta, pd.NA)
    out["uA_Economia_vs_Diesel_R_h"] = ((ua_atual**2 + ua_diesel**2) ** 0.5).where(valid_delta, pd.NA)
    out["uB_Economia_vs_Diesel_R_h"] = ((ub_atual**2 + ub_diesel**2) ** 0.5).where(valid_delta, pd.NA)
    out["uc_Economia_vs_Diesel_R_h"] = ((uc_atual**2 + uc_diesel**2) ** 0.5).where(valid_delta, pd.NA)
    out["U_Economia_vs_Diesel_R_h"] = (K_COVERAGE * pd.to_numeric(out["uc_Economia_vs_Diesel_R_h"], errors="coerce")).where(valid_delta, pd.NA)

    out["Economia_vs_Diesel_pct"] = (100.0 * (pd.to_numeric(out["Razao_Custo_vs_Diesel"], errors="coerce") - 1.0)).where(valid_delta, pd.NA)

    d_pct_d_custo = 100.0 / custo_diesel
    d_pct_d_diesel = -100.0 * custo_atual / (custo_diesel**2)
    ua_pct_from_atual = d_pct_d_custo.abs() * ua_atual
    ua_pct_from_diesel = d_pct_d_diesel.abs() * ua_diesel
    ub_pct_from_atual = d_pct_d_custo.abs() * ub_atual
    ub_pct_from_diesel = d_pct_d_diesel.abs() * ub_diesel
    uc_pct_from_atual = d_pct_d_custo.abs() * uc_atual
    uc_pct_from_diesel = d_pct_d_diesel.abs() * uc_diesel

    out["uA_Economia_vs_Diesel_pct"] = ((ua_pct_from_atual**2 + ua_pct_from_diesel**2) ** 0.5).where(valid_delta, pd.NA)
    out["uB_Economia_vs_Diesel_pct"] = ((ub_pct_from_atual**2 + ub_pct_from_diesel**2) ** 0.5).where(valid_delta, pd.NA)
    out["uc_Economia_vs_Diesel_pct"] = ((uc_pct_from_atual**2 + uc_pct_from_diesel**2) ** 0.5).where(valid_delta, pd.NA)
    out["U_Economia_vs_Diesel_pct"] = (K_COVERAGE * pd.to_numeric(out["uc_Economia_vs_Diesel_pct"], errors="coerce")).where(valid_delta, pd.NA)
    out["delta_over_U_Economia_vs_Diesel_pct"] = (
        pd.to_numeric(out["Economia_vs_Diesel_pct"], errors="coerce")
        / pd.to_numeric(out["U_Economia_vs_Diesel_pct"], errors="coerce")
    ).where(valid_delta, pd.NA)

    diesel_mask = out["Fuel_Label"].astype("string").eq("D85B15") & valid_delta
    out.loc[diesel_mask, "Razao_Custo_vs_Diesel"] = 1.0
    out.loc[diesel_mask, "Economia_vs_Diesel_R_h"] = 0.0
    out.loc[diesel_mask, "Economia_vs_Diesel_pct"] = 0.0
    out.loc[diesel_mask, "delta_over_U_Economia_vs_Diesel_pct"] = 0.0

    interpret = pd.Series(pd.NA, index=out.index, dtype="object")
    economia_pct = pd.to_numeric(out["Economia_vs_Diesel_pct"], errors="coerce")
    interpret.loc[economia_pct.lt(0)] = "economia_vs_diesel"
    interpret.loc[economia_pct.gt(0)] = "piora_vs_diesel"
    interpret.loc[economia_pct.eq(0)] = "igual_ao_diesel"
    out["Interpretacao_Economia_vs_Diesel"] = interpret

    return out.drop(columns=["_diesel_baseline_load_key"], errors="ignore")
