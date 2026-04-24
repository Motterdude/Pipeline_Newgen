from __future__ import annotations

from math import sqrt
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .constants import DT_S, GROUP_COLS_PONTO, GROUP_COLS_TRECHOS, MIN_SAMPLES_PER_WINDOW
from .helpers import (
    find_b_etanol_col,
    get_resolution_for_key,
    has_instrument_key,
    normalize_repeated_stat_tokens,
    res_to_std,
)


def compute_trechos_stats(
    lv_raw: pd.DataFrame,
    instruments: List[Dict[str, Any]],
) -> pd.DataFrame:
    if lv_raw.empty:
        return pd.DataFrame(
            columns=GROUP_COLS_TRECHOS + ["N_samples", "Consumo_kg_h", "uB_Consumo_kg_h"]
        )

    bcol = find_b_etanol_col(lv_raw)

    ignore_cols = set(GROUP_COLS_TRECHOS + ["Index"])
    candidate_cols = [c for c in lv_raw.columns if c not in ignore_cols]

    lv = lv_raw.copy()
    numeric_group_cols = [c for c in GROUP_COLS_TRECHOS if c not in ("BaseName", "WindowID")]
    for c in numeric_group_cols:
        if c in lv.columns:
            lv[c] = pd.to_numeric(lv[c], errors="coerce")
    if candidate_cols:
        lv[candidate_cols] = lv[candidate_cols].apply(pd.to_numeric, errors="coerce")

    g = lv.groupby(GROUP_COLS_TRECHOS, dropna=False, sort=True)
    n_df = g.size().reset_index(name="N_samples")
    valid_groups = n_df[n_df["N_samples"] >= MIN_SAMPLES_PER_WINDOW][GROUP_COLS_TRECHOS].copy()
    if valid_groups.empty:
        return pd.DataFrame(
            columns=GROUP_COLS_TRECHOS + ["N_samples", "Consumo_kg_h", "uB_Consumo_kg_h"]
        )

    lv_valid = lv.merge(valid_groups, on=GROUP_COLS_TRECHOS, how="inner")
    gv = lv_valid.groupby(GROUP_COLS_TRECHOS, dropna=False, sort=True)

    means = gv[candidate_cols].mean(numeric_only=True).add_suffix("_mean").copy()
    first = gv[bcol].first().rename("BEtanol_start")
    last = gv[bcol].last().rename("BEtanol_end")
    n2 = gv.size().rename("N_samples")

    out = pd.concat([means, first, last, n2], axis=1).reset_index().copy()

    out["Delta_BEtanol"] = out["BEtanol_start"] - out["BEtanol_end"]
    out["DeltaT_s"] = (out["N_samples"] - 1) * DT_S
    out["Consumo_kg_h"] = (out["Delta_BEtanol"] / out["DeltaT_s"]) * 3600.0
    out.loc[out["DeltaT_s"] <= 0, "Consumo_kg_h"] = pd.NA

    bal_key = "balance_kg"
    if has_instrument_key(instruments, bal_key):
        res_kg = get_resolution_for_key(instruments, bal_key)
        if res_kg is None or not np.isfinite(res_kg) or res_kg <= 0:
            out["uB_Consumo_kg_h"] = pd.NA
            print("[WARN] balance_kg in instruments but resolution invalid. uB_Consumo_kg_h set to NA.")
        else:
            u_read = res_to_std(res_kg)
            u_delta = sqrt(2) * u_read
            out["uB_Consumo_kg_h"] = (u_delta / out["DeltaT_s"]) * 3600.0
            out.loc[out["DeltaT_s"] <= 0, "uB_Consumo_kg_h"] = pd.NA
    else:
        out["uB_Consumo_kg_h"] = pd.NA

    keep = (
        GROUP_COLS_TRECHOS
        + [c for c in out.columns if c.endswith("_mean")]
        + ["Consumo_kg_h", "uB_Consumo_kg_h", "N_samples"]
    )
    return out[keep].copy()


def compute_ponto_stats(trechos: pd.DataFrame) -> pd.DataFrame:
    if trechos.empty:
        return pd.DataFrame()

    value_cols = [c for c in trechos.columns if c not in GROUP_COLS_PONTO and c != "WindowID"]

    tre = trechos.copy()
    numeric_group_cols = [c for c in GROUP_COLS_PONTO if c != "BaseName"]
    for c in numeric_group_cols:
        if c in tre.columns:
            tre[c] = pd.to_numeric(tre[c], errors="coerce")
    if value_cols:
        tre[value_cols] = tre[value_cols].apply(pd.to_numeric, errors="coerce")

    g = tre.groupby(GROUP_COLS_PONTO, dropna=False, sort=True)

    mean_of_windows = g[value_cols].mean(numeric_only=True).add_suffix("_mean_of_windows").copy()
    sd_of_windows = g[value_cols].std(ddof=1, numeric_only=True).add_suffix("_sd_of_windows").copy()
    mean_of_windows.columns = [normalize_repeated_stat_tokens(c) for c in mean_of_windows.columns]
    sd_of_windows.columns = [normalize_repeated_stat_tokens(c) for c in sd_of_windows.columns]
    n_trechos = g.size().rename("N_trechos_validos")

    out = pd.concat([mean_of_windows, sd_of_windows, n_trechos], axis=1).reset_index().copy()

    uB_col = "uB_Consumo_kg_h"
    if uB_col in tre.columns:
        tmp = tre[GROUP_COLS_PONTO + [uB_col]].copy()
        tmp[uB_col] = pd.to_numeric(tmp[uB_col], errors="coerce")

        sum_u2_df = (
            tmp.groupby(GROUP_COLS_PONTO, dropna=False, sort=True)[uB_col]
            .apply(lambda s: float((s**2).sum()))
            .reset_index(name="sum_u2")
        )
        out = out.merge(sum_u2_df, on=GROUP_COLS_PONTO, how="left").copy()

        N = pd.to_numeric(out["N_trechos_validos"], errors="coerce")
        out["uB_Consumo_kg_h_mean_of_windows"] = (
            pd.to_numeric(out["sum_u2"], errors="coerce") ** 0.5
        ) / N
        out.drop(columns=["sum_u2"], inplace=True)
    else:
        out["uB_Consumo_kg_h_mean_of_windows"] = pd.NA

    return out.copy()
