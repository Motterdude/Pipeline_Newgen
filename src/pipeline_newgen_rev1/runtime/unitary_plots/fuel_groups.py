"""Fuel-blend grouping for unitary plots.

Groups a DataFrame by fuel label (D85B15, E94H6, E75H25, E65H35) for
per-fuel scatter+errorbar rendering.  Port of legacy L3415-5941.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from ..final_table._fuel_defaults import _fuel_blend_labels
from ..final_table._helpers import _to_str_or_empty, _canon_name
from ..final_table.constants import (
    FUEL_H2O_LEVEL_BY_LABEL,
    FUEL_H2O_LEVELS,
)


def _fuel_label_for_group(df: pd.DataFrame) -> str:
    labels = _fuel_blend_labels(df).dropna()
    if labels.empty:
        return ""
    return str(labels.iloc[0]).strip()


def _preferred_fuel_label_order(labels: List[str]) -> List[str]:
    preferred = ["D85B15", "E94H6", "E75H25", "E65H35"]
    uniq: List[str] = []
    seen: set = set()
    for value in labels:
        label = str(value).strip()
        if not label or label in seen:
            continue
        uniq.append(label)
        seen.add(label)
    ordered = [label for label in preferred if label in seen]
    extras = sorted([label for label in uniq if label not in ordered], key=_canon_name)
    return ordered + extras


def _expand_legacy_all_fuels_filter(
    df: pd.DataFrame, fuels_override: Optional[List[int]]
) -> Optional[List[int]]:
    if fuels_override is None:
        return None
    try:
        normalized = sorted({int(float(v)) for v in fuels_override})
    except Exception:
        return fuels_override
    if 0 in normalized:
        return normalized
    if set(normalized) != set(FUEL_H2O_LEVELS):
        return normalized
    h2o = pd.to_numeric(
        df.get("H2O_pct", pd.Series(pd.NA, index=df.index)), errors="coerce"
    )
    if not bool((h2o.abs() <= 0.6).any()):
        return normalized
    return [0] + normalized


def fuel_plot_groups(
    df: pd.DataFrame,
    fuels_override: Optional[List[int]] = None,
) -> List[Tuple[Optional[str], pd.DataFrame]]:
    idx = df.index
    h2o = pd.to_numeric(df.get("H2O_pct", pd.Series(pd.NA, index=idx)), errors="coerce")
    dies = pd.to_numeric(df.get("DIES_pct", pd.Series(pd.NA, index=idx)), errors="coerce")
    biod = pd.to_numeric(df.get("BIOD_pct", pd.Series(pd.NA, index=idx)), errors="coerce")
    fuel_labels = df.get("Fuel_Label", pd.Series(pd.NA, index=idx, dtype="object"))
    fuel_labels = fuel_labels.where(fuel_labels.notna(), _fuel_blend_labels(df))
    fuel_labels = fuel_labels.map(lambda value: _to_str_or_empty(value) or pd.NA).astype("object")

    fuels = _expand_legacy_all_fuels_filter(df, fuels_override)
    selected_h2o_levels: Optional[List[float]] = None
    if fuels is not None:
        try:
            selected_h2o_levels = [float(v) for v in fuels]
        except Exception:
            selected_h2o_levels = None

    labeled_fuels = _preferred_fuel_label_order(fuel_labels.dropna().astype(str).tolist())
    groups: List[Tuple[Optional[str], pd.DataFrame]] = []

    if labeled_fuels:
        selected_labels = labeled_fuels
        if selected_h2o_levels is not None:
            selected_labels = []
            for label in labeled_fuels:
                mapped_level = FUEL_H2O_LEVEL_BY_LABEL.get(label)
                if mapped_level is not None:
                    if any(abs(float(mapped_level) - float(level)) <= 0.6 for level in selected_h2o_levels):
                        selected_labels.append(label)
                    continue

                label_mask = fuel_labels.eq(label)
                label_h2o = h2o.where(label_mask)
                label_dies = dies.where(label_mask)
                label_biod = biod.where(label_mask)

                is_diesel_like = bool(label_dies.gt(0).any() or label_biod.gt(0).any())
                if is_diesel_like and any(abs(float(level)) <= 0.6 for level in selected_h2o_levels):
                    selected_labels.append(label)
                    continue

                matches_level = any(
                    bool((label_h2o.sub(level).abs() <= 0.6).any())
                    for level in selected_h2o_levels
                )
                if matches_level:
                    selected_labels.append(label)

        for label in selected_labels:
            d = df[fuel_labels.eq(label)].copy()
            if not d.empty:
                groups.append((label, d))

    unlabeled = df[fuel_labels.isna()].copy()
    if unlabeled.empty:
        return groups or [(None, df.copy())]

    unlabeled_h2o = pd.to_numeric(
        unlabeled.get("H2O_pct", pd.Series(pd.NA, index=unlabeled.index)), errors="coerce"
    )
    fallback_levels = selected_h2o_levels
    if fallback_levels is None:
        fallback_levels = sorted(float(v) for v in unlabeled_h2o.dropna().unique())

    if not fallback_levels:
        return groups or [(None, df.copy())]

    for h in fallback_levels:
        hv = float(h)
        d = unlabeled[unlabeled_h2o.sub(hv).abs() <= 0.6].copy()
        if d.empty:
            continue
        label = _fuel_label_for_group(d)
        if not label:
            label = f"H2O={int(hv)}%" if hv.is_integer() else f"H2O={hv:g}%"
        groups.append((label, d))

    return groups or [(None, df.copy())]


def series_fuel_plot_groups(
    df: pd.DataFrame,
    fuels_override: Optional[List[int]] = None,
    series_col: Optional[str] = None,
) -> List[Tuple[Optional[str], pd.DataFrame]]:
    if not series_col or series_col not in df.columns:
        return fuel_plot_groups(df, fuels_override=fuels_override)

    sv = df[series_col].map(_to_str_or_empty)
    sv = sv.where(sv.ne(""), "origem_desconhecida")

    groups: List[Tuple[Optional[str], pd.DataFrame]] = []
    for serie in sorted(sv.dropna().unique().tolist()):
        d_series = df[sv.eq(serie)].copy()
        if d_series.empty:
            continue
        for fuel_label, d in fuel_plot_groups(d_series, fuels_override=fuels_override):
            if d.empty:
                continue
            label = str(serie)
            if fuel_label:
                label = f"{serie} | {fuel_label}"
            groups.append((label, d))

    if groups:
        return groups
    return fuel_plot_groups(df, fuels_override=fuels_override)
