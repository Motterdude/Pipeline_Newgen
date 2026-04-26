"""Delta-vs-reference-fuel metrics with GUM uncertainty propagation."""
from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd

from ._diesel_cost_delta import _aggregate_metric_with_uncertainty
from ._fuel_defaults import _fuel_blend_labels
from .constants import K_COVERAGE


_DELTA_VS_REF_SPECS: List[dict] = [
    {
        "value_col": "n_th_pct",
        "uA_col": "uA_n_th_pct",
        "uB_col": "uB_n_th_pct",
        "uc_col": "uc_n_th_pct",
        "U_col": "U_n_th_pct",
        "delta_mode": "diff",
    },
    {
        "value_col": "BSFC_g_kWh",
        "uA_col": "uA_BSFC_g_kWh",
        "uB_col": "uB_BSFC_g_kWh",
        "uc_col": "uc_BSFC_g_kWh",
        "U_col": "U_BSFC_g_kWh",
        "delta_mode": "ratio",
    },
]


def _col_names(value_col: str, delta_mode: str, ref_fuel: str) -> dict:
    tag = "pp" if delta_mode == "diff" else "pct"
    return {
        "ref_value": f"Ref_{ref_fuel}_{value_col}",
        "ref_uc": f"Ref_{ref_fuel}_uc_{value_col}",
        "delta": f"Delta_{tag}_{value_col}_vs_{ref_fuel}",
        "uA_delta": f"uA_Delta_{tag}_{value_col}_vs_{ref_fuel}",
        "uB_delta": f"uB_Delta_{tag}_{value_col}_vs_{ref_fuel}",
        "uc_delta": f"uc_Delta_{tag}_{value_col}_vs_{ref_fuel}",
        "U_delta": f"U_Delta_{tag}_{value_col}_vs_{ref_fuel}",
    }


def _attach_delta_vs_ref_metrics(
    df: pd.DataFrame,
    ref_fuel: str = "D85B15",
) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    idx = out.index

    fuel_labels = out.get("Fuel_Label", pd.Series(pd.NA, index=idx, dtype="object"))
    fuel_labels = fuel_labels.where(fuel_labels.notna(), _fuel_blend_labels(out))
    out["Fuel_Label"] = fuel_labels

    load_key = pd.to_numeric(
        out.get("Load_kW", pd.Series(pd.NA, index=idx)), errors="coerce",
    ).round(6)
    out["_dvr_load_key"] = load_key

    ref_points = out[fuel_labels.eq(ref_fuel)].copy()
    ref_points = ref_points[ref_points["_dvr_load_key"].notna()].copy()

    if ref_points.empty:
        print(f"[WARN] delta_vs_ref | no rows for ref_fuel='{ref_fuel}'; skipping delta columns.")
        for spec in _DELTA_VS_REF_SPECS:
            cn = _col_names(spec["value_col"], spec["delta_mode"], ref_fuel)
            for c in cn.values():
                if c not in out.columns:
                    out[c] = pd.NA
        return out.drop(columns=["_dvr_load_key"], errors="ignore")

    added = 0
    for spec in _DELTA_VS_REF_SPECS:
        value_col = spec["value_col"]
        if value_col not in out.columns:
            continue

        cn = _col_names(value_col, spec["delta_mode"], ref_fuel)
        value_name = f"_ref_{value_col}"

        ref_agg = _aggregate_metric_with_uncertainty(
            ref_points,
            group_cols=["_dvr_load_key"],
            value_col=value_col,
            uA_col=spec["uA_col"],
            uB_col=spec["uB_col"],
            uc_col=spec["uc_col"],
            U_col=spec["U_col"],
            value_name=value_name,
        )
        if ref_agg.empty:
            for c in cn.values():
                if c not in out.columns:
                    out[c] = pd.NA
            continue

        drop_cols = [c for c in ref_agg.columns if c != "_dvr_load_key" and c in out.columns]
        out = out.drop(columns=drop_cols, errors="ignore")
        out = out.merge(ref_agg, on="_dvr_load_key", how="left", suffixes=("", "__drop"))
        out = out.drop(columns=[c for c in out.columns if c.endswith("__drop")], errors="ignore")

        val = pd.to_numeric(out[value_col], errors="coerce")
        ref_val = pd.to_numeric(out[value_name], errors="coerce")
        valid = val.notna() & ref_val.notna()

        out[cn["ref_value"]] = ref_val
        out[cn["ref_uc"]] = pd.to_numeric(out.get(f"uc_{value_name}", pd.NA), errors="coerce")

        uA_val = pd.to_numeric(out.get(spec["uA_col"], pd.NA), errors="coerce")
        uB_val = pd.to_numeric(out.get(spec["uB_col"], pd.NA), errors="coerce")
        uc_val = pd.to_numeric(out.get(spec["uc_col"], pd.NA), errors="coerce")
        uA_ref = pd.to_numeric(out.get(f"uA_{value_name}", pd.NA), errors="coerce")
        uB_ref = pd.to_numeric(out.get(f"uB_{value_name}", pd.NA), errors="coerce")
        uc_ref = pd.to_numeric(out.get(f"uc_{value_name}", pd.NA), errors="coerce")

        if spec["delta_mode"] == "diff":
            out[cn["delta"]] = (val - ref_val).where(valid, pd.NA)
            out[cn["uA_delta"]] = ((uA_val**2 + uA_ref**2) ** 0.5).where(valid, pd.NA)
            out[cn["uB_delta"]] = ((uB_val**2 + uB_ref**2) ** 0.5).where(valid, pd.NA)
            out[cn["uc_delta"]] = ((uc_val**2 + uc_ref**2) ** 0.5).where(valid, pd.NA)
        else:
            safe_ref = ref_val.where(ref_val.abs().gt(0), pd.NA)
            ratio = val / safe_ref
            out[cn["delta"]] = (100.0 * (ratio - 1.0)).where(valid, pd.NA)
            d_dr = 100.0 / safe_ref
            d_dl = -100.0 * val / (safe_ref**2)
            out[cn["uA_delta"]] = (((d_dr * uA_val)**2 + (d_dl * uA_ref)**2) ** 0.5).where(valid, pd.NA)
            out[cn["uB_delta"]] = (((d_dr * uB_val)**2 + (d_dl * uB_ref)**2) ** 0.5).where(valid, pd.NA)
            out[cn["uc_delta"]] = (((d_dr * uc_val)**2 + (d_dl * uc_ref)**2) ** 0.5).where(valid, pd.NA)

        out[cn["U_delta"]] = (K_COVERAGE * pd.to_numeric(out[cn["uc_delta"]], errors="coerce")).where(valid, pd.NA)

        ref_mask = fuel_labels.eq(ref_fuel) & valid
        out.loc[ref_mask, cn["delta"]] = 0.0

        agg_temp = [value_name, f"uA_{value_name}", f"uB_{value_name}",
                    f"uc_{value_name}", f"U_{value_name}", "n_points"]
        out = out.drop(columns=[c for c in agg_temp if c in out.columns], errors="ignore")
        added += 1

    out = out.drop(columns=["_dvr_load_key"], errors="ignore")
    if added:
        print(f"[OK] delta_vs_ref | added delta columns for {added} metric(s) vs {ref_fuel}.")
    return out
