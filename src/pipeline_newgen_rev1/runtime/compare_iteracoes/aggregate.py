"""GUM-compliant statistical aggregation for compare_iteracoes.

Key rules (decisions 2026-04-25):
- uA (random/aleatoria): RSS / N — reduced by averaging (IID).
- uB (systematic/sistematica): RSS / N — NOT reduced (100% correlated within campaign).
- uc = sqrt(uA^2 + uB^2), with fallback to RSS-of-uc / N when uA/uB absent.
- U = K_COVERAGE * uc (K=2.0, ~95% confidence).
"""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from .specs import K_COVERAGE


def _rss_or_na(values: pd.Series) -> float:
    v = pd.to_numeric(values, errors="coerce").dropna()
    if v.empty:
        return float("nan")
    return float(np.sqrt(np.sum(np.square(v.to_numpy(dtype=float)))))


def aggregate_by_load_point(
    df: pd.DataFrame,
    *,
    value_name: str,
    group_cols: List[str] | None = None,
) -> pd.DataFrame:
    if group_cols is None:
        group_cols = ["_campaign_bl_adtv", "_sentido_plot", "Load_kW"]

    out_cols = group_cols + [
        value_name,
        f"uA_{value_name}",
        f"uB_{value_name}",
        f"uc_{value_name}",
        f"U_{value_name}",
        "n_points",
    ]
    if df is None or df.empty:
        return pd.DataFrame(columns=out_cols)

    tmp = df.copy()
    for c in group_cols + ["_metric", "_uA", "_uB", "_uc", "_U"]:
        if c not in tmp.columns:
            tmp[c] = pd.NA

    tmp = tmp.dropna(subset=group_cols).copy()
    for c in ["_metric", "_uA", "_uB", "_uc", "_U"]:
        tmp[c] = pd.to_numeric(tmp[c], errors="coerce")
    tmp = tmp.dropna(subset=["_metric"]).copy()
    if tmp.empty:
        return pd.DataFrame(columns=out_cols)

    g = (
        tmp.groupby(group_cols, dropna=False, sort=True)
        .agg(
            **{
                value_name: ("_metric", "mean"),
                "n_points": ("_metric", "count"),
                "_uA_rss": ("_uA", _rss_or_na),
                "_uB_rss": ("_uB", _rss_or_na),
                "_uc_rss": ("_uc", _rss_or_na),
                "_U_rss": ("_U", _rss_or_na),
            }
        )
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
        g[f"uc_{value_name}"].notna(),
        g["_uc_rss"] / n,
    )
    g[f"U_{value_name}"] = K_COVERAGE * pd.to_numeric(g[f"uc_{value_name}"], errors="coerce")
    g[f"U_{value_name}"] = g[f"U_{value_name}"].where(
        g[f"U_{value_name}"].notna(),
        g["_U_rss"] / n,
    )

    return g[out_cols].copy()


def mean_subida_descida(df: pd.DataFrame, *, value_name: str) -> pd.DataFrame:
    """Average subida and descida for each campaign × Load_kW.

    uB (systematic, same instrument in same campaign) is 100% correlated:
    uB(mean) = (uB_sub + uB_des) / 2  — does NOT shrink. GUM §F.1.2.4.

    uA (random, IID between windows):
    uA(mean) = sqrt(uA_sub^2 + uA_des^2) / 2.

    Fallback for derived metrics without uA/uB split:
    uc(mean) = (uc_sub + uc_des) / 2  — treated as 100% systematic.
    """
    out_cols = [
        "_campaign_bl_adtv", "Load_kW", value_name,
        f"uA_{value_name}", f"uB_{value_name}", f"uc_{value_name}", f"U_{value_name}",
        "n_points",
    ]
    if df is None or df.empty:
        return pd.DataFrame(columns=out_cols)

    sub = df[df["_sentido_plot"].eq("subida")].copy()
    des = df[df["_sentido_plot"].eq("descida")].copy()
    if sub.empty and des.empty:
        return pd.DataFrame(columns=out_cols)

    if sub.empty:
        m = des.rename(columns={c: f"{c}_des" for c in des.columns if c not in ("_campaign_bl_adtv", "Load_kW")})
        for c in [value_name, f"uA_{value_name}", f"uB_{value_name}", f"uc_{value_name}", f"U_{value_name}", "n_points"]:
            m[f"{c}_sub"] = pd.NA
    elif des.empty:
        m = sub.rename(columns={c: f"{c}_sub" for c in sub.columns if c not in ("_campaign_bl_adtv", "Load_kW")})
        for c in [value_name, f"uA_{value_name}", f"uB_{value_name}", f"uc_{value_name}", f"U_{value_name}", "n_points"]:
            m[f"{c}_des"] = pd.NA
    else:
        m = sub.merge(des, on=["_campaign_bl_adtv", "Load_kW"], how="outer", suffixes=("_sub", "_des"))
    if m.empty:
        return pd.DataFrame(columns=out_cols)

    def _num(col: str) -> pd.Series:
        return pd.to_numeric(m.get(col, pd.Series(pd.NA, index=m.index)), errors="coerce")

    value_sub = _num(f"{value_name}_sub")
    value_des = _num(f"{value_name}_des")
    ua_sub = _num(f"uA_{value_name}_sub")
    ua_des = _num(f"uA_{value_name}_des")
    ub_sub = _num(f"uB_{value_name}_sub")
    ub_des = _num(f"uB_{value_name}_des")
    uc_sub = _num(f"uc_{value_name}_sub")
    uc_des = _num(f"uc_{value_name}_des")
    U_sub = _num(f"U_{value_name}_sub")
    U_des = _num(f"U_{value_name}_des")

    both = value_sub.notna() & value_des.notna()
    only_sub = value_sub.notna() & value_des.isna()
    only_des = value_sub.isna() & value_des.notna()

    out = pd.DataFrame()
    out["_campaign_bl_adtv"] = m["_campaign_bl_adtv"]
    out["Load_kW"] = pd.to_numeric(m["Load_kW"], errors="coerce")
    out[value_name] = pd.NA
    out.loc[both, value_name] = (value_sub[both] + value_des[both]) / 2.0
    out.loc[only_sub, value_name] = value_sub[only_sub]
    out.loc[only_des, value_name] = value_des[only_des]

    out[f"uA_{value_name}"] = pd.NA
    out.loc[both, f"uA_{value_name}"] = (ua_sub[both]**2 + ua_des[both]**2) ** 0.5 / 2.0
    out.loc[only_sub, f"uA_{value_name}"] = ua_sub[only_sub]
    out.loc[only_des, f"uA_{value_name}"] = ua_des[only_des]

    out[f"uB_{value_name}"] = pd.NA
    out.loc[both, f"uB_{value_name}"] = (ub_sub[both] + ub_des[both]) / 2.0
    out.loc[only_sub, f"uB_{value_name}"] = ub_sub[only_sub]
    out.loc[only_des, f"uB_{value_name}"] = ub_des[only_des]

    ua_out = pd.to_numeric(out[f"uA_{value_name}"], errors="coerce")
    ub_out = pd.to_numeric(out[f"uB_{value_name}"], errors="coerce")
    out[f"uc_{value_name}"] = (ua_out**2 + ub_out**2) ** 0.5
    uc_fallback = pd.NA
    uc_both = (uc_sub + uc_des) / 2.0
    out[f"uc_{value_name}"] = out[f"uc_{value_name}"].where(
        out[f"uc_{value_name}"].notna(),
        uc_both.where(both, uc_sub.where(only_sub, uc_des)),
    )
    out[f"U_{value_name}"] = K_COVERAGE * pd.to_numeric(out[f"uc_{value_name}"], errors="coerce")

    out["n_points"] = (
        pd.to_numeric(m.get("n_points_sub", 0), errors="coerce").fillna(0)
        + pd.to_numeric(m.get("n_points_des", 0), errors="coerce").fillna(0)
    )
    return out[out_cols].sort_values("Load_kW").copy()
