"""Campaign scanner: detect experimental structure from discovered input files.

Scans the already-parsed InputFileMeta list and builds a CampaignCatalog
that describes fuel groups, load points, directions, and iteration mode.
Downstream stages use the catalog to drive comparisons and plot grouping
without hardcoding assumptions about "baseline/aditivado" or "subida/descida".
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..adapters import DiscoveredRuntimeInputs, InputFileMeta
from .fuel_properties import _fuel_label_from_components


_DIRECTION_UP = re.compile(r"\b(?:subindo|subida|up)\b", re.IGNORECASE)
_DIRECTION_DOWN = re.compile(r"\b(?:descendo|descida|down)\b", re.IGNORECASE)
_CAMPAIGN_BASELINE = re.compile(r"\b(?:baseline|base|referencia|ref)\b", re.IGNORECASE)
_CAMPAIGN_TREATMENT = re.compile(r"\b(?:aditivado|aditiv|treated|treatment)\b", re.IGNORECASE)


@dataclass(frozen=True)
class CampaignCatalog:
    fuel_labels: List[str]
    load_points: List[float]
    directions: List[str]
    campaigns: List[str]
    iteration_mode: str
    file_count_by_fuel: Dict[str, int]
    file_count_by_campaign: Dict[str, int]
    file_count_by_direction: Dict[str, int]
    total_files: int = 0


def fuel_label_from_meta(meta: InputFileMeta) -> str:
    return _fuel_label_from_components(
        meta.dies_pct, meta.biod_pct, meta.etoh_pct, meta.h2o_pct,
    )


def _normalize_folder_text(path_str: str) -> str:
    return str(path_str or "").replace("_", " ").replace("-", " ").replace("\\", "/")


def infer_direction_from_path(path_str: str) -> Optional[str]:
    text = _normalize_folder_text(path_str)
    if _DIRECTION_UP.search(text):
        return "subida"
    if _DIRECTION_DOWN.search(text):
        return "descida"
    return None


def infer_campaign_from_path(path_str: str) -> Optional[str]:
    text = _normalize_folder_text(path_str)
    if _CAMPAIGN_BASELINE.search(text):
        return "baseline"
    if _CAMPAIGN_TREATMENT.search(text):
        return "aditivado"
    return None


def _detect_iteration_mode(
    *,
    n_fuels: int,
    n_directions: int,
    n_campaigns: int,
) -> str:
    has_directions = n_directions >= 2
    has_campaigns = n_campaigns >= 2
    has_fuels = n_fuels >= 2

    if has_campaigns and has_directions:
        return "direction"
    if has_campaigns:
        return "direction"
    if has_fuels and not has_directions:
        return "fuel"
    if has_fuels and has_directions:
        return "direction"
    if has_directions:
        return "direction"
    return "fuel"


def scan_campaign_structure(
    discovery: DiscoveredRuntimeInputs,
    *,
    source_types: Sequence[str] = ("LABVIEW",),
) -> CampaignCatalog:
    fuel_counter: Counter[str] = Counter()
    load_set: set[float] = set()
    direction_counter: Counter[str] = Counter()
    campaign_counter: Counter[str] = Counter()
    total = 0

    for meta in discovery.files:
        if meta.source_type not in source_types:
            continue
        total += 1

        label = fuel_label_from_meta(meta)
        if label:
            fuel_counter[label] += 1

        if meta.load_kw is not None and isfinite(meta.load_kw):
            load_set.add(meta.load_kw)

        path_str = str(meta.path.parent)
        direction = infer_direction_from_path(path_str)
        if direction:
            direction_counter[direction] += 1

        campaign = infer_campaign_from_path(path_str)
        if campaign:
            campaign_counter[campaign] += 1

    fuel_labels = sorted(fuel_counter.keys())
    load_points = sorted(load_set)
    directions = sorted(direction_counter.keys())
    campaigns = sorted(campaign_counter.keys())

    iteration_mode = _detect_iteration_mode(
        n_fuels=len(fuel_labels),
        n_directions=len(directions),
        n_campaigns=len(campaigns),
    )

    return CampaignCatalog(
        fuel_labels=fuel_labels,
        load_points=load_points,
        directions=directions,
        campaigns=campaigns,
        iteration_mode=iteration_mode,
        file_count_by_fuel=dict(fuel_counter),
        file_count_by_campaign=dict(campaign_counter),
        file_count_by_direction=dict(direction_counter),
        total_files=total,
    )


def summarize_campaign_catalog(catalog: CampaignCatalog) -> Dict[str, Any]:
    return {
        "iteration_mode": catalog.iteration_mode,
        "fuel_labels": catalog.fuel_labels,
        "load_points": catalog.load_points,
        "directions": catalog.directions,
        "campaigns": catalog.campaigns,
        "file_count_by_fuel": catalog.file_count_by_fuel,
        "file_count_by_campaign": catalog.file_count_by_campaign,
        "file_count_by_direction": catalog.file_count_by_direction,
        "total_files": catalog.total_files,
    }


def default_comparison_pairs(catalog: CampaignCatalog) -> List[Tuple[str, str]]:
    if catalog.iteration_mode == "direction" and catalog.campaigns:
        pairs = []
        if len(catalog.campaigns) >= 2:
            for d in (catalog.directions or [""]):
                left = f"{catalog.campaigns[0]}_{d}" if d else catalog.campaigns[0]
                right = f"{catalog.campaigns[1]}_{d}" if d else catalog.campaigns[1]
                pairs.append((left, right))
            if catalog.directions:
                left_mean = f"{catalog.campaigns[0]}_media"
                right_mean = f"{catalog.campaigns[1]}_media"
                pairs.append((left_mean, right_mean))
        return pairs

    if len(catalog.fuel_labels) < 2:
        return []
    reference = catalog.fuel_labels[0]
    return [(reference, other) for other in catalog.fuel_labels[1:]]
