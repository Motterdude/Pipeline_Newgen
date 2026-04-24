"""Shared constants for the final-table subpackage."""
from __future__ import annotations

from math import sqrt

K_COVERAGE = 2.0

COMPOSITION_COLS = ["DIES_pct", "BIOD_pct", "EtOH_pct", "H2O_pct"]

FUEL_H2O_LEVELS = [6, 25, 35]
FUEL_BLEND_DEFAULTS = {
    "D85B15": {"density_param": "FUEL_DENSITY_KG_M3_D85B15", "cost_param": "FUEL_COST_R_L_D85B15"},
    "E94H6":  {"density_param": "FUEL_DENSITY_KG_M3_E94H6",  "cost_param": "FUEL_COST_R_L_E94H6"},
    "E75H25": {"density_param": "FUEL_DENSITY_KG_M3_E75H25", "cost_param": "FUEL_COST_R_L_E75H25"},
    "E65H35": {"density_param": "FUEL_DENSITY_KG_M3_E65H35", "cost_param": "FUEL_COST_R_L_E65H35"},
}
FUEL_LABEL_BY_H2O_LEVEL = {0: "D85B15", 6: "E94H6", 25: "E75H25", 35: "E65H35"}
FUEL_H2O_LEVEL_BY_LABEL = {label: level for level, label in FUEL_LABEL_BY_H2O_LEVEL.items()}
SCENARIO_REFERENCE_FUEL_LABEL = "E94H6"

MACHINE_SCENARIO_SPECS = [
    {"key": "Colheitadeira", "label": "Colheitadeira",
     "hours_param": "MACHINE_HOURS_PER_YEAR_COLHEITADEIRA",
     "diesel_l_h_param": "MACHINE_DIESEL_L_H_COLHEITADEIRA", "color": "#1f77b4"},
    {"key": "Trator_Transbordo", "label": "Trator transbordo",
     "hours_param": "MACHINE_HOURS_PER_YEAR_TRATOR_TRANSBORDO",
     "diesel_l_h_param": "MACHINE_DIESEL_L_H_TRATOR_TRANSBORDO", "color": "#ff7f0e"},
    {"key": "Caminhao", "label": "Caminhao",
     "hours_param": "MACHINE_HOURS_PER_YEAR_CAMINHAO",
     "diesel_l_h_param": "MACHINE_DIESEL_L_H_CAMINHAO", "color": "#2ca02c"},
]

# Airflow assumptions
AFR_STOICH_E94H6 = 8.4
ETHANOL_FRAC_E94H6 = 0.94
AFR_STOICH_ETHANOL = 9.0
AFR_STOICH_BIODIESEL = 12.5
AFR_STOICH_DIESEL = 14.5
LAMBDA_DEFAULT = 1.0
R_AIR_DRY_J_KG_K = 287.058

# Psychrometrics / cp models
R_V_WATER = 461.5
CP_WATER_VAPOR_KJ_KG_K = 1.86

# Exhaust emissions helpers
MW_CO2_KG_KMOL = 44.0095
MW_CO_KG_KMOL = 28.0101
MW_O2_KG_KMOL = 31.9988
MW_N2_KG_KMOL = 28.0134
MW_H2O_KG_KMOL = 18.0153
MW_C3H8_KG_KMOL = 44.097
MW_NO_KG_KMOL = 30.006
MW_NO2_KG_KMOL = 46.0055

H_MASS_FRAC_DIESEL = 0.1385641540557986
H_MASS_FRAC_BIODIESEL = 0.12238992225838548
H_MASS_FRAC_ETHANOL = 0.1312813388612733
THC_LOW_SIGNAL_WARN_PPM = 10.0


def rect_to_std(limit):
    import pandas as pd
    return pd.to_numeric(limit, errors="coerce") / sqrt(3)


def res_to_std(step: float) -> float:
    return step / sqrt(12) if step > 0 else 0.0
