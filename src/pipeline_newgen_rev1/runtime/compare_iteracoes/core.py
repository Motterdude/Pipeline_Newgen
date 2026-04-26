"""Orchestrator for the compare_iteracoes processing pipeline.

Resolves config requests, prepares metric points, aggregates with GUM
uncertainty, builds series frames, computes deltas, and returns a
consolidated result for downstream export and plotting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import pandas as pd

from .aggregate import aggregate_by_load_point
from .delta import build_delta_table
from .prepare import prepare_compare_points, prepare_consumo_points
from .series import build_series_frames, build_series_frames_dynamic
from .specs import (
    COMPARE_ITER_METRIC_SPECS_BY_ID,
    COMPARE_ITER_SERIES_META,
    build_series_meta_from_catalog,
    compare_iter_pair_context,
)

if TYPE_CHECKING:
    from ..campaign_scan import CampaignCatalog


@dataclass
class CompareResult:
    delta_table: pd.DataFrame
    series_by_metric: Dict[str, Dict[str, pd.DataFrame]]
    requests: List[Dict[str, Any]]


def _is_blank_cell(x: object) -> bool:
    if x is None:
        return True
    try:
        if pd.isna(x):
            return True
    except Exception:
        pass
    s = str(x).replace("﻿", "").strip()
    return s == "" or s.lower() == "nan"


def _to_str(x: object) -> str:
    return "" if _is_blank_cell(x) else str(x).replace("﻿", "").strip()


def _row_enabled(v: object) -> bool:
    if _is_blank_cell(v):
        return False
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    try:
        return bool(int(float(s)))
    except Exception:
        return False


def _uncertainty_flags(row: dict) -> Tuple[bool, bool]:
    with_raw = _to_str(row.get("with_uncertainty", "")).lower()
    without_raw = _to_str(row.get("without_uncertainty", "")).lower()
    true_vals = {"1", "true", "yes", "on", "y", "checked"}
    defined_vals = true_vals | {"0", "false", "no", "off", "n", "unchecked"}

    with_flag = with_raw in true_vals
    without_flag = without_raw in true_vals
    with_defined = with_raw in defined_vals
    without_defined = without_raw in defined_vals

    if not with_defined and not without_defined:
        mode = _to_str(row.get("show_uncertainty", "auto")).lower()
        if mode in {"off", "disable", "disabled", "none", "0", "false", "no", "na", "n/a"}:
            return False, True
        if mode in {"both", "all", "dual", "on_off"}:
            return True, True
        return True, False

    if not with_flag and not without_flag:
        return True, False
    return with_flag, without_flag


def _uncertainty_variants(row: dict) -> List[Tuple[str, str, bool]]:
    with_flag, without_flag = _uncertainty_flags(row)
    both = with_flag and without_flag
    variants: List[Tuple[str, str, bool]] = []
    if with_flag:
        variants.append(("with_uncertainty", "on", both))
    if without_flag:
        variants.append(("without_uncertainty", "off", both))
    if not variants:
        variants.append(("with_uncertainty", "on", False))
    return variants


def _default_compare_pairs(catalog: Optional[CampaignCatalog] = None) -> List[Tuple[str, str]]:
    if catalog is not None and catalog.iteration_mode == "fuel":
        from ..campaign_scan import default_comparison_pairs
        return default_comparison_pairs(catalog)
    return [
        ("baseline_media", "aditivado_media"),
        ("baseline_subida", "aditivado_subida"),
        ("baseline_descida", "aditivado_descida"),
    ]


def _build_default_requests(pairs: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    reqs: List[Dict[str, Any]] = []
    for metric_id in COMPARE_ITER_METRIC_SPECS_BY_ID:
        for left_id, right_id in pairs:
            reqs.append({
                "left_id": left_id,
                "right_id": right_id,
                "metric_id": metric_id,
                "variant_key": "with_uncertainty",
                "show_uncertainty": "on",
                "dual_variant": False,
                "source": "fallback_pairs",
            })
    return reqs


def resolve_requests(
    compare_df: Optional[pd.DataFrame],
    *,
    fallback_pairs: Optional[List[Tuple[str, str]]] = None,
    catalog: Optional[CampaignCatalog] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    pairs = fallback_pairs or _default_compare_pairs(catalog)
    if compare_df is None or compare_df.empty:
        return _build_default_requests(pairs), "fallback_pairs"

    series_meta = build_series_meta_from_catalog(catalog)
    rows = compare_df.to_dict(orient="records")
    enabled_rows = [r for r in rows if _row_enabled((r or {}).get("enabled", ""))]
    if not enabled_rows:
        return [], "gui_empty"

    requests: List[Dict[str, Any]] = []
    dedupe: set = set()
    for row_idx, row in enumerate(enabled_rows, start=1):
        left_id = _to_str(row.get("left_series", "")).lower()
        right_id = _to_str(row.get("right_series", "")).lower()
        metric_id = _to_str(row.get("metric_id", "")).lower()

        if left_id not in series_meta or right_id not in series_meta:
            print(f"[WARN] compare_iteracoes: linha {row_idx} series invalidas ('{left_id}' vs '{right_id}').")
            continue
        if left_id == right_id:
            print(f"[WARN] compare_iteracoes: linha {row_idx} series iguais ('{left_id}').")
            continue
        if metric_id not in COMPARE_ITER_METRIC_SPECS_BY_ID:
            print(f"[WARN] compare_iteracoes: linha {row_idx} metrica invalida ('{metric_id}').")
            continue

        for variant_key, show_uncertainty, dual_variant in _uncertainty_variants(row):
            key = (left_id, right_id, metric_id, variant_key)
            if key in dedupe:
                continue
            dedupe.add(key)
            requests.append({
                "left_id": left_id,
                "right_id": right_id,
                "metric_id": metric_id,
                "variant_key": variant_key,
                "show_uncertainty": show_uncertainty,
                "dual_variant": bool(dual_variant),
                "source": "gui_compare_tab",
            })

    if not requests:
        is_catalog_mismatch = (
            catalog is not None
            and catalog.iteration_mode == "fuel"
            and not fallback_pairs
        )
        if is_catalog_mismatch:
            fallback = _default_compare_pairs(catalog)
            if fallback:
                print("[INFO] compare_iteracoes: GUI rows use legacy series but catalog is fuel mode — using default pairs.")
                return _build_default_requests(fallback), "fallback_after_gui_mismatch"
        return [], "gui_invalid"
    return requests, "gui_compare_tab"


def compute_compare_iteracoes(
    final_table: pd.DataFrame,
    compare_df: Optional[pd.DataFrame],
    mappings: dict,
    *,
    pairs_override: Optional[List[Dict[str, Any]]] = None,
    catalog: Optional[CampaignCatalog] = None,
) -> CompareResult:
    if pairs_override:
        requests, source = pairs_override, "cli_override"
    else:
        requests, source = resolve_requests(compare_df, catalog=catalog)
    if not requests:
        print(f"[INFO] compute_compare_iteracoes | no requests (source={source}).")
        return CompareResult(delta_table=pd.DataFrame(), series_by_metric={}, requests=[])

    series_meta = build_series_meta_from_catalog(catalog)
    is_fuel_mode = catalog is not None and catalog.iteration_mode == "fuel"
    group_cols = (
        ["_campaign_bl_adtv", "Load_kW"] if is_fuel_mode
        else ["_campaign_bl_adtv", "_sentido_plot", "Load_kW"]
    )

    series_by_metric: Dict[str, Dict[str, pd.DataFrame]] = {}
    delta_rows: List[pd.DataFrame] = []

    metrics_seen: set = set()
    for req in requests:
        metric_id = req["metric_id"]

        if metric_id not in metrics_seen:
            metrics_seen.add(metric_id)
            spec = COMPARE_ITER_METRIC_SPECS_BY_ID[metric_id]
            metric_col = spec["metric_col"]
            value_name = spec["value_name"]

            if metric_col == "__consumo__":
                prepared = prepare_consumo_points(final_table, catalog=catalog)
            else:
                prepared = prepare_compare_points(
                    final_table, metric_col=metric_col, mappings=mappings, catalog=catalog,
                )

            if prepared.empty:
                print(f"[WARN] compute_compare_iteracoes | no data for {metric_id}.")
                continue

            agg = aggregate_by_load_point(prepared, value_name=value_name, group_cols=group_cols)
            if agg.empty:
                continue

            frames = build_series_frames_dynamic(agg, value_name=value_name, catalog=catalog)
            series_by_metric[metric_id] = frames

        if metric_id not in series_by_metric:
            continue

        frames = series_by_metric[metric_id]
        spec = COMPARE_ITER_METRIC_SPECS_BY_ID[metric_id]
        value_name = spec["value_name"]

        left_id = req["left_id"]
        right_id = req["right_id"]
        left_df = frames.get(left_id)
        right_df = frames.get(right_id)
        if left_df is None or right_df is None or left_df.empty or right_df.empty:
            continue

        pair_ctx = compare_iter_pair_context(left_id, right_id, series_meta=series_meta)
        variant_key = req.get("variant_key", "with_uncertainty")

        delta = build_delta_table(
            left_df, right_df,
            value_name=value_name,
            label_left=pair_ctx["left_label"],
            label_right=pair_ctx["right_label"],
            interpret_neg=pair_ctx["interpret_neg"],
            interpret_pos=pair_ctx["interpret_pos"],
            delta_mode=spec.get("delta_mode", "ratio"),
        )
        if not delta.empty:
            suffix = "" if variant_key == "with_uncertainty" else f" ({variant_key})"
            delta = delta.copy()
            delta["Metrica"] = spec["title"]
            delta["Comparacao"] = pair_ctx["pair_title"] + suffix
            delta["Incerteza"] = "com" if variant_key == "with_uncertainty" else "sem"
            delta["delta_mode"] = spec.get("delta_mode", "ratio")
            delta_rows.append(delta)

    if delta_rows:
        all_deltas = pd.concat(delta_rows, ignore_index=True)
        all_deltas["Load_kW"] = pd.to_numeric(all_deltas["Load_kW"], errors="coerce")
        all_deltas = all_deltas.sort_values(["Metrica", "Comparacao", "Load_kW"]).copy()
    else:
        all_deltas = pd.DataFrame()

    print(f"[OK] compute_compare_iteracoes | {len(delta_rows)} delta tables, "
          f"{len(all_deltas)} total rows, {len(series_by_metric)} metrics.")
    return CompareResult(delta_table=all_deltas, series_by_metric=series_by_metric, requests=requests)
