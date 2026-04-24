"""Registro das grandezas auditadas pelo audit layer.

A `MeasurandSpec` descreve, para cada grandeza que queremos auditar:
- `key`: sufixo canônico usado nos nomes das colunas no `final_table` (ex: `Consumo_kg_h`).
  As colunas existentes no `final_table` seguem a convenção `uA_<key>`, `uB_<key>`,
  `uc_<key>`, `U_<key>`.
- `value_col`: coluna do `final_table` com o valor medido/derivado.
- `sd_col`: coluna do SD bruto entre janelas (quando existe; `None` para derivadas puras).
- `instrument_key`: chave em `instruments_df` para decompor uB em resolução vs acurácia.
  `None` para derivadas (a decomposição virá por propagação das fontes).
- `kind`: "measured" (lida direto de um instrumento) ou "derived" (calculada a partir de outras).
- `derived_from`: para `kind="derived"`, tupla de `keys` de `AUDITED_MEASURANDS` usadas
  na propagação. Permite o audit layer validar que as fontes têm uA/uB disponíveis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class MeasurandSpec:
    key: str
    value_col: str
    kind: str  # "measured" | "derived"
    sd_col: Optional[str] = None
    instrument_key: Optional[str] = None
    derived_from: Tuple[str, ...] = ()


AUDITED_MEASURANDS: Tuple[MeasurandSpec, ...] = (
    # --- Medidas diretas ---
    MeasurandSpec(
        key="Consumo_kg_h",
        value_col="Consumo_kg_h_mean_of_windows",
        sd_col="Consumo_kg_h_sd_of_windows",
        # Não tem instrumento direto: Consumo_kg_h é DERIVADO de balance_kg × dt.
        # O uB já vem propagado de compute_trechos_stats (u_delta_balance / ΔT × 3600).
        # Deixar instrument_key=None evita reportar uB_res/uB_acc em unidade errada.
        instrument_key=None,
        kind="measured",
    ),
    MeasurandSpec(
        key="P_kw",
        value_col="Potência Total_mean_of_windows",
        sd_col="Potência Total_sd_of_windows",
        instrument_key="power_kw",
        kind="measured",
    ),
    MeasurandSpec(
        key="NOx_ppm",
        value_col="NOX_mean_of_windows",
        sd_col="NOX_sd_of_windows",
        instrument_key="nox_ppm",
        kind="measured",
    ),
    MeasurandSpec(
        key="CO_pct",
        value_col="CO_mean_of_windows",
        sd_col="CO_sd_of_windows",
        instrument_key="co_pct",
        kind="measured",
    ),
    MeasurandSpec(
        key="CO2_pct",
        value_col="CO2_mean_of_windows",
        sd_col="CO2_sd_of_windows",
        instrument_key="co2_pct",
        kind="measured",
    ),
    MeasurandSpec(
        key="THC_ppm",
        value_col="THC_mean_of_windows",
        sd_col="THC_sd_of_windows",
        instrument_key="thc_ppm",
        kind="measured",
    ),
    # --- Derivadas ---
    MeasurandSpec(
        key="Consumo_L_h",
        value_col="Consumo_L_h",
        kind="derived",
        derived_from=("Consumo_kg_h",),  # density é uB-only, contabilizado via FUEL_DENSITY_KG_M3_*
    ),
    MeasurandSpec(
        key="n_th_pct",
        value_col="n_th_pct",
        kind="derived",
        derived_from=("P_kw", "Consumo_kg_h"),  # + LHV (uB-only)
    ),
    MeasurandSpec(
        key="BSFC_g_kWh",
        value_col="BSFC_g_kWh",
        kind="derived",
        derived_from=("Consumo_kg_h", "P_kw"),
    ),
    MeasurandSpec(
        key="NOx_g_kWh",
        value_col="NOx_g_kWh",
        kind="derived",
        derived_from=("NOx_ppm", "P_kw", "Consumo_kg_h"),
    ),
    MeasurandSpec(
        key="CO_g_kWh",
        value_col="CO_g_kWh",
        kind="derived",
        derived_from=("CO_pct", "P_kw", "Consumo_kg_h"),
    ),
    MeasurandSpec(
        key="CO2_g_kWh",
        value_col="CO2_g_kWh",
        kind="derived",
        derived_from=("CO2_pct", "P_kw", "Consumo_kg_h"),
    ),
    MeasurandSpec(
        key="THC_g_kWh",
        value_col="THC_g_kWh",
        kind="derived",
        derived_from=("THC_ppm", "P_kw", "Consumo_kg_h"),
    ),
)


def audited_measurands_by_key() -> dict:
    return {spec.key: spec for spec in AUDITED_MEASURANDS}
