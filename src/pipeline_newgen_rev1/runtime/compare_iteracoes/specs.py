"""Constants and metadata for the compare_iteracoes pipeline."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from ..campaign_scan import CampaignCatalog

K_COVERAGE = 2.0

COMPARE_ITER_SERIES_META: Dict[str, Dict[str, str]] = {
    "baseline_media": {"label": "Baseline media", "slug": "baseline_media"},
    "baseline_subida": {"label": "Baseline subida", "slug": "baseline_subida"},
    "baseline_descida": {"label": "Baseline descida", "slug": "baseline_descida"},
    "aditivado_media": {"label": "Aditivado media", "slug": "aditivado_media"},
    "aditivado_subida": {"label": "Aditivado subida", "slug": "aditivado_subida"},
    "aditivado_descida": {"label": "Aditivado descida", "slug": "aditivado_descida"},
}


def build_series_meta_from_catalog(catalog: Optional[CampaignCatalog]) -> Dict[str, Dict[str, str]]:
    if catalog is None or catalog.iteration_mode == "direction":
        return COMPARE_ITER_SERIES_META
    meta: Dict[str, Dict[str, str]] = {}
    for fuel in catalog.fuel_labels:
        meta[fuel] = {"label": fuel, "slug": fuel}
    return meta

COMPARE_ITER_METRIC_SPECS: List[Dict[str, str]] = [
    {
        "metric_id": "consumo",
        "metric_col": "__consumo__",
        "value_name": "consumo_kg_h",
        "title": "Consumo absoluto",
        "y_label": "Consumo absoluto (kg/h)",
        "filename_slug": "consumo_abs",
        "delta_mode": "ratio",
    },
    {
        "metric_id": "co2",
        "metric_col": "CO2_mean_of_windows",
        "value_name": "co2_medido",
        "title": "CO2 medido",
        "y_label": "CO2 medido (%)",
        "filename_slug": "co2_medido",
        "delta_mode": "diff",
    },
    {
        "metric_id": "co",
        "metric_col": "CO_mean_of_windows",
        "value_name": "co_medido",
        "title": "CO medido",
        "y_label": "CO medido (ppm)",
        "filename_slug": "co_medido",
        # diff (nao ratio): CO opera no chao de ruido do analisador (mediana ~0.005 %vol,
        # ~37% das leituras negativas/oscilando em torno de zero). O delta percentual
        # 100*(adt/base-1) explode quando o Baseline ~= 0 e nao tem significado fisico.
        # O delta absoluto (com U_delta propagado via GUM) e a metrica honesta aqui.
        "delta_mode": "diff",
    },
    {
        "metric_id": "o2",
        "metric_col": "O2_mean_of_windows",
        "value_name": "o2_medido",
        "title": "O2 medido",
        "y_label": "O2 medido (%)",
        "filename_slug": "o2_medido",
        "delta_mode": "diff",
    },
    {
        "metric_id": "nox",
        "metric_col": "NOX_mean_of_windows",
        "value_name": "nox_medido",
        "title": "NOX medido",
        "y_label": "NOX medido (ppm)",
        "filename_slug": "nox_medido",
        "delta_mode": "ratio",
    },
    {
        "metric_id": "thc",
        "metric_col": "THC_mean_of_windows",
        "value_name": "thc_medido",
        "title": "THC medido",
        "y_label": "THC medido (ppm)",
        "filename_slug": "thc_medido",
        "delta_mode": "ratio",
    },
    {
        "metric_id": "co2_g_kwh",
        "metric_col": "CO2_g_kWh",
        "value_name": "co2_g_kwh",
        "title": "CO2 especifico",
        "y_label": "CO2 especifico (g/kWh)",
        "filename_slug": "co2_g_kwh",
        "delta_mode": "ratio",
    },
    {
        "metric_id": "co_g_kwh",
        "metric_col": "CO_g_kWh",
        "value_name": "co_g_kwh",
        "title": "CO especifico",
        "y_label": "CO especifico (g/kWh)",
        "filename_slug": "co_g_kwh",
        # diff (nao ratio): derivado do mesmo CO de chao de ruido — ver nota em metric_id "co".
        "delta_mode": "diff",
    },
    {
        "metric_id": "nox_g_kwh",
        "metric_col": "NOx_g_kWh",
        "value_name": "nox_g_kwh",
        "title": "NOx especifico",
        "y_label": "NOx especifico (g/kWh)",
        "filename_slug": "nox_g_kwh",
        "delta_mode": "ratio",
    },
    {
        "metric_id": "thc_g_kwh",
        "metric_col": "THC_g_kWh",
        "value_name": "thc_g_kwh",
        "title": "THC especifico",
        "y_label": "THC especifico (g/kWh)",
        "filename_slug": "thc_g_kwh",
        "delta_mode": "ratio",
    },
    {
        "metric_id": "n_th",
        "metric_col": "n_th_pct",
        "value_name": "n_th_pct",
        "title": "Eficiencia termica",
        "y_label": "eta_th (%)",
        "filename_slug": "n_th_pct",
        "delta_mode": "diff",
    },
    {
        "metric_id": "n_th_ind",
        "metric_col": "n_th_ind_pct",
        "value_name": "n_th_ind_pct",
        "title": "Eficiencia termica indicada",
        "y_label": "eta_th_ind (%)",
        "filename_slug": "n_th_ind_pct",
        "delta_mode": "diff",
    },
    {
        "metric_id": "bsfc",
        "metric_col": "BSFC_g_kWh",
        "value_name": "bsfc_g_kwh",
        "title": "BSFC",
        "y_label": "BSFC (g/kWh)",
        "filename_slug": "bsfc_g_kwh",
        "delta_mode": "ratio",
    },
    {
        "metric_id": "bsfc_vol",
        "metric_col": "BSFC_L_kWh",
        "value_name": "bsfc_l_kwh",
        "title": "BSFC volumetrico",
        "y_label": "BSFC (L/kWh)",
        "filename_slug": "bsfc_l_kwh",
        "delta_mode": "ratio",
    },
    {
        "metric_id": "bsfc_fin",
        "metric_col": "BSFC_R_kWh",
        "value_name": "bsfc_r_kwh",
        "title": "BSFC financeiro",
        "y_label": "BSFC (R$/kWh)",
        "filename_slug": "bsfc_r_kwh",
        "delta_mode": "ratio",
    },
    {
        "metric_id": "mfb_10_90",
        "metric_col": "MFB_10_90",
        "value_name": "mfb_10_90",
        "title": "MFB 10-90",
        "y_label": "MFB 10-90 (degCA)",
        "filename_slug": "mfb_10_90",
        "delta_mode": "diff",
    },
    {
        "metric_id": "mfb_10_50",
        "metric_col": "MFB_10_50",
        "value_name": "mfb_10_50",
        "title": "MFB 10-50",
        "y_label": "MFB 10-50 (degCA)",
        "filename_slug": "mfb_10_50",
        "delta_mode": "diff",
    },
    {
        "metric_id": "mfb_50_90",
        "metric_col": "MFB_50_90",
        "value_name": "mfb_50_90",
        "title": "MFB 50-90",
        "y_label": "MFB 50-90 (degCA)",
        "filename_slug": "mfb_50_90",
        "delta_mode": "diff",
    },
    {
        "metric_id": "ai10",
        "metric_col": "KIBOX_AI10_1",
        "value_name": "kibox_ai10",
        "title": "AI10",
        "y_label": "AI10 (degCA BTDC)",
        "filename_slug": "ai10",
        "delta_mode": "diff",
    },
    {
        "metric_id": "ai50",
        "metric_col": "KIBOX_AI50_1",
        "value_name": "kibox_ai50",
        "title": "AI50",
        "y_label": "AI50 (degCA ATDC)",
        "filename_slug": "ai50",
        "delta_mode": "diff",
    },
    {
        "metric_id": "ai90",
        "metric_col": "KIBOX_AI90_1",
        "value_name": "kibox_ai90",
        "title": "AI90",
        "y_label": "AI90 (degCA ATDC)",
        "filename_slug": "ai90",
        "delta_mode": "diff",
    },
    {
        "metric_id": "p_coletor",
        "metric_col": "P_COLETOR_RAW_mean_of_windows",
        "value_name": "p_coletor_kpa",
        "title": "P_COLETOR",
        "y_label": "P_COLETOR (kPa)",
        "filename_slug": "p_coletor",
        "delta_mode": "diff",
    },
    {
        "metric_id": "p_e_turb",
        "metric_col": "P_E_TURB_RAW_mean_of_windows",
        "value_name": "p_e_turb_kpa",
        "title": "P_E_TURB",
        "y_label": "P_E_TURB (kPa)",
        "filename_slug": "p_e_turb",
        "delta_mode": "diff",
    },
    {
        "metric_id": "p_s_comp",
        "metric_col": "P_S_COMP_RAW_mean_of_windows",
        "value_name": "p_s_comp_kpa",
        "title": "P_S_COMP",
        "y_label": "P_S_COMP (kPa)",
        "filename_slug": "p_s_comp",
        "delta_mode": "diff",
    },
    {
        "metric_id": "p_s_turb",
        "metric_col": "P_S_TURB_RAW_mean_of_windows",
        "value_name": "p_s_turb_kpa",
        "title": "P_S_TURB",
        "y_label": "P_S_TURB (kPa)",
        "filename_slug": "p_s_turb",
        "delta_mode": "diff",
    },
    {
        "metric_id": "t_admissao",
        "metric_col": "T_ADMISSAO_mean_of_windows",
        "value_name": "t_admissao_c",
        "title": "T_ADMISSAO",
        "y_label": "T_ADMISSAO (C)",
        "filename_slug": "t_admissao",
        "delta_mode": "diff",
    },
    {
        "metric_id": "t_e_comp",
        "metric_col": "T_E_COMP_mean_of_windows",
        "value_name": "t_e_comp_c",
        "title": "T_E_COMP",
        "y_label": "T_E_COMP (C)",
        "filename_slug": "t_e_comp",
        "delta_mode": "diff",
    },
    {
        "metric_id": "t_e_turb",
        "metric_col": "T_E_TURB_mean_of_windows",
        "value_name": "t_e_turb_c",
        "title": "T_E_TURB",
        "y_label": "T_E_TURB (C)",
        "filename_slug": "t_e_turb",
        "delta_mode": "diff",
    },
    {
        "metric_id": "t_s_agua",
        "metric_col": "T_S_AGUA_mean_of_windows",
        "value_name": "t_s_agua_c",
        "title": "T_S_AGUA",
        "y_label": "T_S_AGUA (C)",
        "filename_slug": "t_s_agua",
        "delta_mode": "diff",
    },
    {
        "metric_id": "t_s_comp",
        "metric_col": "T_S_COMP_mean_of_windows",
        "value_name": "t_s_comp_c",
        "title": "T_S_COMP",
        "y_label": "T_S_COMP (C)",
        "filename_slug": "t_s_comp",
        "delta_mode": "diff",
    },
    {
        "metric_id": "t_s_turb",
        "metric_col": "T_S_TURB_mean_of_windows",
        "value_name": "t_s_turb_c",
        "title": "T_S_TURB",
        "y_label": "T_S_TURB (C)",
        "filename_slug": "t_s_turb",
        "delta_mode": "diff",
    },
    {
        "metric_id": "apmax",
        "metric_col": "KIBOX_APMAX_1",
        "value_name": "kibox_apmax",
        "title": "APMAX",
        "y_label": "APMAX (degCA ATDC)",
        "filename_slug": "apmax",
        "delta_mode": "diff",
    },
    {
        "metric_id": "pmax",
        "metric_col": "KIBOX_PMAX_1",
        "value_name": "kibox_pmax",
        "title": "PMAX",
        "y_label": "PMAX (bar)",
        "filename_slug": "pmax",
        "delta_mode": "ratio",
    },
    {
        "metric_id": "aqmax",
        "metric_col": "KIBOX_AQMAX_1",
        "value_name": "kibox_aqmax",
        "title": "AQMAX",
        "y_label": "AQMAX (degCA)",
        "filename_slug": "aqmax",
        "delta_mode": "diff",
    },
    {
        "metric_id": "rmax",
        "metric_col": "KIBOX_RMAX_1",
        "value_name": "kibox_rmax",
        "title": "RMAX",
        "y_label": "RMAX (bar/degCA)",
        "filename_slug": "rmax",
        "delta_mode": "ratio",
    },
    {
        "metric_id": "imeph",
        "metric_col": "KIBOX_IMEPH_1",
        "value_name": "kibox_imeph",
        "title": "IMEPH",
        "y_label": "IMEPH (bar)",
        "filename_slug": "imeph",
        "delta_mode": "ratio",
    },
    {
        "metric_id": "imepl",
        "metric_col": "KIBOX_IMEPL_1",
        "value_name": "kibox_imepl",
        "title": "IMEPL",
        "y_label": "IMEPL (bar)",
        "filename_slug": "imepl",
        "delta_mode": "diff",
    },
    {
        "metric_id": "imepn",
        "metric_col": "KIBOX_IMEPN_1",
        "value_name": "kibox_imepn",
        "title": "IMEPN",
        "y_label": "IMEPN (bar)",
        "filename_slug": "imepn",
        "delta_mode": "ratio",
    },
    {
        "metric_id": "imepn_cov",
        "metric_col": "KIBOX_IMEPN_COV_1",
        "value_name": "kibox_imepn_cov",
        "title": "IMEPN COV",
        "y_label": "IMEPN COV (%)",
        "filename_slug": "imepn_cov",
        "delta_mode": "diff",
    },
    {
        "metric_id": "qmax",
        "metric_col": "KIBOX_QMAX_1",
        "value_name": "kibox_qmax",
        "title": "QMAX",
        "y_label": "QMAX (J/degCA)",
        "filename_slug": "qmax",
        "delta_mode": "ratio",
    },
]

COMPARE_ITER_METRIC_SPECS_BY_ID: Dict[str, Dict[str, str]] = {
    str(spec.get("metric_id", "")).strip().lower(): spec
    for spec in COMPARE_ITER_METRIC_SPECS
    if str(spec.get("metric_id", "")).strip()
}


def metric_spec_for_id(metric_id: str) -> Optional[Dict[str, str]]:
    return COMPARE_ITER_METRIC_SPECS_BY_ID.get(str(metric_id).strip().lower())


def compare_iter_pair_context(
    left_id: str,
    right_id: str,
    series_meta: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, str]:
    meta = series_meta or COMPARE_ITER_SERIES_META
    left_meta = meta.get(left_id, {"label": left_id, "slug": left_id})
    right_meta = meta.get(right_id, {"label": right_id, "slug": right_id})
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
