"""Delta computation with GUM uncertainty propagation and significance testing."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .specs import K_COVERAGE


def build_delta_table(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    *,
    value_name: str,
    label_left: str,
    label_right: str,
    interpret_neg: str,
    interpret_pos: str,
) -> pd.DataFrame:
    if left_df is None or left_df.empty or right_df is None or right_df.empty:
        return pd.DataFrame()

    base_cols = [
        "Load_kW", value_name,
        f"uA_{value_name}", f"uB_{value_name}", f"uc_{value_name}", f"U_{value_name}",
        "n_points",
    ]
    left = left_df.copy()
    right = right_df.copy()
    for c in base_cols:
        if c not in left.columns:
            left[c] = pd.NA
        if c not in right.columns:
            right[c] = pd.NA

    left = left[base_cols].rename(columns={
        value_name: "value_left",
        f"uA_{value_name}": "uA_left",
        f"uB_{value_name}": "uB_left",
        f"uc_{value_name}": "uc_left",
        f"U_{value_name}": "U_left",
        "n_points": "n_points_left",
    })
    right = right[base_cols].rename(columns={
        value_name: "value_right",
        f"uA_{value_name}": "uA_right",
        f"uB_{value_name}": "uB_right",
        f"uc_{value_name}": "uc_right",
        f"U_{value_name}": "U_right",
        "n_points": "n_points_right",
    })

    m = left.merge(right, on="Load_kW", how="inner")
    if m.empty:
        return pd.DataFrame()

    for c in m.columns:
        m[c] = pd.to_numeric(m[c], errors="coerce")

    m = m.dropna(subset=["Load_kW", "value_left", "value_right"]).copy()
    m = m[(m["value_left"] != 0) & (m["value_right"] != 0)].copy()
    if m.empty:
        return pd.DataFrame()

    m["delta_abs"] = m["value_right"] - m["value_left"]
    m["ratio_right_over_left"] = m["value_right"] / m["value_left"]
    m["delta_pct"] = 100.0 * (m["ratio_right_over_left"] - 1.0)

    d_dr = 100.0 / m["value_left"]
    d_dl = -100.0 * m["value_right"] / (m["value_left"] ** 2)

    m["uA_delta_pct"] = ((d_dr.abs() * m["uA_right"]) ** 2 + (d_dl.abs() * m["uA_left"]) ** 2) ** 0.5
    m["uB_delta_pct"] = ((d_dr.abs() * m["uB_right"]) ** 2 + (d_dl.abs() * m["uB_left"]) ** 2) ** 0.5

    # Primary: propagate via uc directly (GUM §5). Works for derived metrics
    # (e.g. n_th) that only track uc, not uA/uB separately.
    m["uc_delta_pct"] = ((d_dr.abs() * m["uc_right"]) ** 2 + (d_dl.abs() * m["uc_left"]) ** 2) ** 0.5
    # Fallback: sqrt(uA^2 + uB^2) if direct uc path yielded NaN.
    uc_fallback = (m["uA_delta_pct"] ** 2 + m["uB_delta_pct"] ** 2) ** 0.5
    m["uc_delta_pct"] = m["uc_delta_pct"].where(m["uc_delta_pct"].notna(), uc_fallback)

    m["U_delta_pct"] = K_COVERAGE * m["uc_delta_pct"]
    m["delta_over_U"] = m["delta_pct"] / m["U_delta_pct"]
    m["label_left"] = label_left
    m["label_right"] = label_right
    m["interpretacao"] = np.where(m["delta_pct"] < 0, interpret_neg, interpret_pos)
    m["significancia_95pct"] = np.where(
        m["delta_pct"].abs() > m["U_delta_pct"],
        "diferenca_maior_que_U",
        "diferenca_dentro_de_U",
    )
    return m.sort_values("Load_kW").copy()
