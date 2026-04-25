"""Build series frames from aggregated data.

Direction mode: 6 frames (baseline/aditivado x subida/descida/media).
Fuel mode: 1 frame per fuel label (no direction split).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

import pandas as pd

from .aggregate import mean_subida_descida

if TYPE_CHECKING:
    from ..campaign_scan import CampaignCatalog


def build_series_frames(agg: pd.DataFrame, *, value_name: str) -> Dict[str, pd.DataFrame]:
    subida = agg[agg["_sentido_plot"].eq("subida")].copy()
    descida = agg[agg["_sentido_plot"].eq("descida")].copy()
    media_sd = mean_subida_descida(agg, value_name=value_name)
    return {
        "baseline_subida": subida[subida["_campaign_bl_adtv"].eq("baseline")].copy(),
        "baseline_descida": descida[descida["_campaign_bl_adtv"].eq("baseline")].copy(),
        "baseline_media": media_sd[media_sd["_campaign_bl_adtv"].eq("baseline")].copy(),
        "aditivado_subida": subida[subida["_campaign_bl_adtv"].eq("aditivado")].copy(),
        "aditivado_descida": descida[descida["_campaign_bl_adtv"].eq("aditivado")].copy(),
        "aditivado_media": media_sd[media_sd["_campaign_bl_adtv"].eq("aditivado")].copy(),
    }


def build_series_frames_dynamic(
    agg: pd.DataFrame,
    *,
    value_name: str,
    catalog: Optional[CampaignCatalog] = None,
) -> Dict[str, pd.DataFrame]:
    if catalog is None or catalog.iteration_mode == "direction":
        return build_series_frames(agg, value_name=value_name)
    frames: Dict[str, pd.DataFrame] = {}
    for group_id in agg["_campaign_bl_adtv"].unique():
        if not group_id:
            continue
        frames[str(group_id)] = agg[agg["_campaign_bl_adtv"].eq(group_id)].copy()
    return frames
