"""Native MoTeC trechos/ponto aggregation.

Replaces ``legacy.compute_motec_trechos_stats`` (L5031-5057) and
``legacy.compute_motec_ponto_stats`` (L5060-5081).
"""
from __future__ import annotations

import pandas as pd

from .trechos_ponto.constants import MIN_SAMPLES_PER_WINDOW
from .trechos_ponto.helpers import normalize_repeated_stat_tokens

MOTEC_GROUP_COLS_TRECHOS = [
    "BaseName", "Load_kW", "DIES_pct", "BIOD_pct", "EtOH_pct", "H2O_pct", "WindowID",
]
MOTEC_GROUP_COLS_PONTO = [
    "Load_kW", "DIES_pct", "BIOD_pct", "EtOH_pct", "H2O_pct",
]


def compute_motec_trechos_stats(motec_raw: pd.DataFrame) -> pd.DataFrame:
    if motec_raw.empty:
        return pd.DataFrame()

    ignore_cols = set(MOTEC_GROUP_COLS_TRECHOS + ["Index"])
    candidate_cols = [c for c in motec_raw.columns if c not in ignore_cols]

    mot = motec_raw.copy()
    numeric_group_cols = [c for c in MOTEC_GROUP_COLS_TRECHOS if c not in ("BaseName", "WindowID")]
    for c in numeric_group_cols:
        if c in mot.columns:
            mot[c] = pd.to_numeric(mot[c], errors="coerce")
    if candidate_cols:
        mot[candidate_cols] = mot[candidate_cols].apply(pd.to_numeric, errors="coerce")

    g = mot.groupby(MOTEC_GROUP_COLS_TRECHOS, dropna=False, sort=True)
    n_df = g.size().reset_index(name="Motec_N_samples")
    valid_groups = n_df[n_df["Motec_N_samples"] >= MIN_SAMPLES_PER_WINDOW][MOTEC_GROUP_COLS_TRECHOS].copy()
    if valid_groups.empty:
        return pd.DataFrame(columns=MOTEC_GROUP_COLS_TRECHOS + ["Motec_N_samples"])

    mot_valid = mot.merge(valid_groups, on=MOTEC_GROUP_COLS_TRECHOS, how="inner")
    gv = mot_valid.groupby(MOTEC_GROUP_COLS_TRECHOS, dropna=False, sort=True)

    means = gv[candidate_cols].mean(numeric_only=True).add_suffix("_mean")
    n2 = gv.size().rename("Motec_N_samples")

    out = pd.concat([means, n2], axis=1).reset_index()
    keep = MOTEC_GROUP_COLS_TRECHOS + [c for c in out.columns if c.endswith("_mean")] + ["Motec_N_samples"]
    return out[keep]


def compute_motec_ponto_stats(motec_trechos: pd.DataFrame) -> pd.DataFrame:
    if motec_trechos.empty:
        return pd.DataFrame(columns=MOTEC_GROUP_COLS_PONTO)

    value_cols = [
        c for c in motec_trechos.columns
        if c not in set(MOTEC_GROUP_COLS_PONTO + ["BaseName", "WindowID", "Motec_N_samples"])
    ]

    mot = motec_trechos.copy()
    for c in MOTEC_GROUP_COLS_PONTO:
        if c in mot.columns:
            mot[c] = pd.to_numeric(mot[c], errors="coerce")
    if value_cols:
        mot[value_cols] = mot[value_cols].apply(pd.to_numeric, errors="coerce")

    g = mot.groupby(MOTEC_GROUP_COLS_PONTO, dropna=False, sort=True)
    mean_of_windows = g[value_cols].mean(numeric_only=True).add_suffix("_mean_of_windows")
    sd_of_windows = g[value_cols].std(ddof=1, numeric_only=True).add_suffix("_sd_of_windows")
    mean_of_windows.columns = [normalize_repeated_stat_tokens(c) for c in mean_of_windows.columns]
    sd_of_windows.columns = [normalize_repeated_stat_tokens(c) for c in sd_of_windows.columns]
    n_trechos = g.size().rename("Motec_N_trechos_validos")
    n_files = g["BaseName"].nunique().rename("Motec_N_files")
    mean_samples = g["Motec_N_samples"].mean().rename("Motec_N_samples_mean_of_windows")

    out = pd.concat([mean_of_windows, sd_of_windows, n_trechos, n_files, mean_samples], axis=1).reset_index()
    return out
