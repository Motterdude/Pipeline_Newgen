"""Constants and metadata for the compare_iteracoes pipeline."""
from __future__ import annotations

from typing import Dict, List, Optional

K_COVERAGE = 2.0

COMPARE_ITER_SERIES_META: Dict[str, Dict[str, str]] = {
    "baseline_media": {"label": "Baseline media", "slug": "baseline_media"},
    "baseline_subida": {"label": "Baseline subida", "slug": "baseline_subida"},
    "baseline_descida": {"label": "Baseline descida", "slug": "baseline_descida"},
    "aditivado_media": {"label": "Aditivado media", "slug": "aditivado_media"},
    "aditivado_subida": {"label": "Aditivado subida", "slug": "aditivado_subida"},
    "aditivado_descida": {"label": "Aditivado descida", "slug": "aditivado_descida"},
}

COMPARE_ITER_METRIC_SPECS: List[Dict[str, str]] = [
    {
        "metric_id": "consumo",
        "metric_col": "__consumo__",
        "value_name": "consumo_kg_h",
        "title": "Consumo absoluto",
        "y_label": "Consumo absoluto (kg/h)",
        "filename_slug": "consumo_abs",
    },
    {
        "metric_id": "co2",
        "metric_col": "CO2_mean_of_windows",
        "value_name": "co2_medido",
        "title": "CO2 medido",
        "y_label": "CO2 medido (%)",
        "filename_slug": "co2_medido",
    },
    {
        "metric_id": "co",
        "metric_col": "CO_mean_of_windows",
        "value_name": "co_medido",
        "title": "CO medido",
        "y_label": "CO medido (ppm)",
        "filename_slug": "co_medido",
    },
    {
        "metric_id": "o2",
        "metric_col": "O2_mean_of_windows",
        "value_name": "o2_medido",
        "title": "O2 medido",
        "y_label": "O2 medido (%)",
        "filename_slug": "o2_medido",
    },
    {
        "metric_id": "nox",
        "metric_col": "NOX_mean_of_windows",
        "value_name": "nox_medido",
        "title": "NOX medido",
        "y_label": "NOX medido (ppm)",
        "filename_slug": "nox_medido",
    },
    {
        "metric_id": "thc",
        "metric_col": "THC_mean_of_windows",
        "value_name": "thc_medido",
        "title": "THC medido",
        "y_label": "THC medido (ppm)",
        "filename_slug": "thc_medido",
    },
    {
        "metric_id": "co2_g_kwh",
        "metric_col": "CO2_g_kWh",
        "value_name": "co2_g_kwh",
        "title": "CO2 especifico",
        "y_label": "CO2 especifico (g/kWh)",
        "filename_slug": "co2_g_kwh",
    },
    {
        "metric_id": "co_g_kwh",
        "metric_col": "CO_g_kWh",
        "value_name": "co_g_kwh",
        "title": "CO especifico",
        "y_label": "CO especifico (g/kWh)",
        "filename_slug": "co_g_kwh",
    },
    {
        "metric_id": "nox_g_kwh",
        "metric_col": "NOx_g_kWh",
        "value_name": "nox_g_kwh",
        "title": "NOx especifico",
        "y_label": "NOx especifico (g/kWh)",
        "filename_slug": "nox_g_kwh",
    },
    {
        "metric_id": "thc_g_kwh",
        "metric_col": "THC_g_kWh",
        "value_name": "thc_g_kwh",
        "title": "THC especifico",
        "y_label": "THC especifico (g/kWh)",
        "filename_slug": "thc_g_kwh",
    },
    {
        "metric_id": "n_th",
        "metric_col": "n_th_pct",
        "value_name": "n_th_pct",
        "title": "Eficiencia termica",
        "y_label": "eta_th (%)",
        "filename_slug": "n_th_pct",
    },
]

COMPARE_ITER_METRIC_SPECS_BY_ID: Dict[str, Dict[str, str]] = {
    str(spec.get("metric_id", "")).strip().lower(): spec
    for spec in COMPARE_ITER_METRIC_SPECS
    if str(spec.get("metric_id", "")).strip()
}


def metric_spec_for_id(metric_id: str) -> Optional[Dict[str, str]]:
    return COMPARE_ITER_METRIC_SPECS_BY_ID.get(str(metric_id).strip().lower())


def compare_iter_pair_context(left_id: str, right_id: str) -> Dict[str, str]:
    left_meta = COMPARE_ITER_SERIES_META[left_id]
    right_meta = COMPARE_ITER_SERIES_META[right_id]
    return {
        "left_label": left_meta["label"],
        "right_label": right_meta["label"],
        "pair_slug": f"{left_meta['slug']}_vs_{right_meta['slug']}",
        "pair_title": f"{left_meta['label']} vs {right_meta['label']}",
        "line_label": f"{right_meta['label']} vs {left_meta['label']}",
        "note_text": f"Negativo = {right_meta['label']} menor; Positivo = {right_meta['label']} maior",
        "interpret_neg": f"{right_meta['slug']}_menor",
        "interpret_pos": f"{right_meta['slug']}_maior",
    }
