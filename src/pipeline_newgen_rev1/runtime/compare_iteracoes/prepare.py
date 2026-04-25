"""Point preparation for compare_iteracoes: campaign/direction extraction,
uncertainty column resolution, and metric-specific filtering."""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, Optional, Tuple

import pandas as pd


def _canon_name(x: object) -> str:
    s = str(x).replace("﻿", "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s)


def campaign_from_basename(basename: object) -> str:
    s = _canon_name(basename).replace(" ", "_").replace("-", "_")
    if not s:
        return ""
    if ("baseline_1" in s) or ("bl_1" in s) or ("baseline" in s):
        return "baseline"
    if ("aditivado_1" in s) or ("adtv_1" in s) or ("aditivado" in s) or ("adtv" in s):
        return "aditivado"
    return ""


def sentido_from_row(row: pd.Series) -> str:
    sent = _canon_name(row.get("Sentido_Carga", ""))
    if "subida" in sent or "subindo" in sent or re.search(r"\bup\b", sent):
        return "subida"
    if "descida" in sent or "descendo" in sent or re.search(r"\bdown\b", sent):
        return "descida"

    base = _canon_name(row.get("BaseName", ""))
    if "subindo" in base or "subida" in base:
        return "subida"
    if "descendo" in base or "descida" in base:
        return "descida"
    return ""


def find_consumo_col(df: pd.DataFrame) -> Optional[str]:
    for c in ["Consumo_kg_h_mean_of_windows", "Consumo_kg_h", "Fuel_kg_h", "fuel_kgh_mean_of_windows"]:
        if c in df.columns:
            return c
    for c in df.columns:
        cl = str(c).lower()
        if ("consumo" in cl) and ("mean_of_windows" in cl):
            return c
    return None


def _apply_diesel_filter(df: pd.DataFrame) -> pd.DataFrame:
    if ("DIES_pct" not in df.columns) and ("BIOD_pct" not in df.columns):
        return df
    dies = pd.to_numeric(df.get("DIES_pct", pd.Series(pd.NA, index=df.index)), errors="coerce")
    biod = pd.to_numeric(df.get("BIOD_pct", pd.Series(pd.NA, index=df.index)), errors="coerce")
    mask = dies.gt(0) | biod.gt(0)
    if mask.any():
        return df[mask].copy()
    return df


def _prefix_from_key_norm(key_norm: str) -> str:
    fixed = {
        "power_kw": "P_kw",
        "fuel_kgh": "Consumo_kg_h",
        "lhv_kj_kg": "LHV_kJ_kg",
        "co_pct": "CO_pct",
        "co2_pct": "CO2_pct",
        "o2_pct": "O2_pct",
        "nox_ppm": "NOx_ppm",
        "no_ppm": "NO_ppm",
        "thc_ppm": "THC_ppm",
    }
    return fixed.get(key_norm, key_norm.upper())


def _resolve_col(df: pd.DataFrame, col_req: str) -> str:
    if col_req in df.columns:
        return col_req
    cl = col_req.lower()
    for c in df.columns:
        if str(c).lower() == cl:
            return c
    raise KeyError(col_req)


def guess_uncertainty_col(df: pd.DataFrame, y_col: str, mappings: dict) -> Optional[str]:
    candidates = [f"U_{y_col}"]
    for key_norm, spec in mappings.items():
        col_mean_req = str(spec.get("mean", "")).strip()
        if not col_mean_req:
            continue
        try:
            mapped_mean = _resolve_col(df, col_mean_req)
        except Exception:
            continue
        if mapped_mean == y_col:
            cand = f"U_{_prefix_from_key_norm(key_norm)}"
            if cand not in candidates:
                candidates.append(cand)
    for cand in candidates:
        if cand not in df.columns:
            continue
        vals = pd.to_numeric(df[cand], errors="coerce")
        if vals.notna().any():
            return cand
    return None


def metric_uncertainty_cols(df: pd.DataFrame, metric_col: str, mappings: dict) -> Tuple[str, str, str, str]:
    U_col = guess_uncertainty_col(df, metric_col, mappings) or f"U_{metric_col}"
    suffix = U_col[2:] if U_col.startswith("U_") else metric_col
    return f"uA_{suffix}", f"uB_{suffix}", f"uc_{suffix}", U_col


def prepare_compare_points(
    df: pd.DataFrame,
    *,
    metric_col: str,
    mappings: dict,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if "BaseName" not in df.columns:
        print("[WARN] compare iteracoes: coluna BaseName ausente. Pulei.")
        return pd.DataFrame()
    if metric_col not in df.columns:
        print(f"[WARN] compare iteracoes: coluna '{metric_col}' nao encontrada no output. Pulei.")
        return pd.DataFrame()

    out = df.copy()
    out["_campaign_bl_adtv"] = out["BaseName"].map(campaign_from_basename)
    out["_sentido_plot"] = out.apply(sentido_from_row, axis=1)
    out = _apply_diesel_filter(out)

    uA_col, uB_col, uc_col, U_col = metric_uncertainty_cols(out, metric_col, mappings)
    out["Load_kW"] = pd.to_numeric(out.get("Load_kW", pd.NA), errors="coerce")
    out["_metric"] = pd.to_numeric(out.get(metric_col, pd.NA), errors="coerce")
    out["_uA"] = pd.to_numeric(out.get(uA_col, pd.NA), errors="coerce")
    out["_uB"] = pd.to_numeric(out.get(uB_col, pd.NA), errors="coerce")
    out["_uc"] = pd.to_numeric(out.get(uc_col, pd.NA), errors="coerce")
    out["_U"] = pd.to_numeric(out.get(U_col, pd.NA), errors="coerce")

    out = out[
        out["_campaign_bl_adtv"].isin(["baseline", "aditivado"])
        & out["_sentido_plot"].isin(["subida", "descida"])
    ].copy()
    out = out.dropna(subset=["Load_kW", "_metric"]).copy()
    return out


def prepare_consumo_points(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if "BaseName" not in df.columns:
        print("[WARN] compare iteracoes BL vs ADTV: coluna BaseName ausente. Pulei.")
        return pd.DataFrame()

    consumo_col = find_consumo_col(df)
    if not consumo_col:
        print("[WARN] compare iteracoes BL vs ADTV: coluna de consumo nao encontrada. Pulei.")
        return pd.DataFrame()

    out = df.copy()
    out["_campaign_bl_adtv"] = out["BaseName"].map(campaign_from_basename)
    out["_sentido_plot"] = out.apply(sentido_from_row, axis=1)
    out = _apply_diesel_filter(out)

    out["Load_kW"] = pd.to_numeric(out.get("Load_kW", pd.NA), errors="coerce")
    out["_metric"] = pd.to_numeric(out[consumo_col], errors="coerce")
    out["_uA"] = pd.to_numeric(out.get("uA_Consumo_kg_h", pd.NA), errors="coerce")
    out["_uB"] = pd.to_numeric(out.get("uB_Consumo_kg_h", pd.NA), errors="coerce")
    out["_uc"] = pd.to_numeric(out.get("uc_Consumo_kg_h", pd.NA), errors="coerce")
    out["_U"] = pd.to_numeric(out.get("U_Consumo_kg_h", pd.NA), errors="coerce")

    out = out[
        out["_campaign_bl_adtv"].isin(["baseline", "aditivado"])
        & out["_sentido_plot"].isin(["subida", "descida"])
    ].copy()
    out = out.dropna(subset=["Load_kW", "_metric"]).copy()
    return out
