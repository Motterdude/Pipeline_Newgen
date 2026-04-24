from __future__ import annotations

B_ETANOL_COL_CANDIDATES = ["B_Etanol", "B_ETANOL", "B_ETANOL (kg)", "B_Etanol (kg)"]

MIN_SAMPLES_PER_WINDOW = 30
DT_S = 1.0

GROUP_COLS_TRECHOS = [
    "BaseName", "Load_kW", "DIES_pct", "BIOD_pct",
    "EtOH_pct", "H2O_pct", "WindowID",
]
GROUP_COLS_PONTO = [
    "BaseName", "Load_kW", "DIES_pct", "BIOD_pct",
    "EtOH_pct", "H2O_pct",
]
