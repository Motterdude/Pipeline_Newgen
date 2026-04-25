"""Build the 6 series frames (baseline/aditivado x subida/descida/media)
from an aggregated DataFrame."""
from __future__ import annotations

from typing import Dict

import pandas as pd

from .aggregate import mean_subida_descida


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
