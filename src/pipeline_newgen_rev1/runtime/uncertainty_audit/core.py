"""Orquestrador do audit layer de incerteza.

Para cada `MeasurandSpec` em `AUDITED_MEASURANDS`, o `enrich_final_table_with_audit`
adiciona colunas de auditoria ao `final_table`:

- `uB_res_<key>` — componente de resolução do uB
- `uB_acc_<key>` — componente de acurácia do uB
- `pct_uA_contrib_<key>` — %uA_contrib variance-weighted (GUM §F.1.2.4)
- `pct_uB_contrib_<key>` — 100 − %uA_contrib

Para derivadas sem uA/uB separados (só uc), o audit layer computa o split natively.
Nunca sobrescreve colunas pré-existentes: se `uA_<key>` já existe, preserva.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .contribution import contribution_var
from .decomposition import decompose_uB
from .derived_propagation import (
    propagate_bsfc,
    propagate_consumo_L_h,
    propagate_emission_gkwh,
    propagate_n_th,
)
from .specs import AUDITED_MEASURANDS, MeasurandSpec


# Map MeasurandSpec.key → (função de propagação, kwargs extras)
_DERIVED_PROPAGATORS = {
    "Consumo_L_h": (propagate_consumo_L_h, {}),
    "n_th_pct": (propagate_n_th, {}),
    "BSFC_g_kWh": (propagate_bsfc, {}),
    "NOx_g_kWh": (propagate_emission_gkwh, {"value_col": "NOx_g_kWh", "conc_col_mean": "NOX_mean_of_windows", "conc_prefix": "NOx_ppm"}),
    "CO_g_kWh": (propagate_emission_gkwh, {"value_col": "CO_g_kWh", "conc_col_mean": "CO_mean_of_windows", "conc_prefix": "CO_pct"}),
    "CO2_g_kWh": (propagate_emission_gkwh, {"value_col": "CO2_g_kWh", "conc_col_mean": "CO2_mean_of_windows", "conc_prefix": "CO2_pct"}),
    "THC_g_kWh": (propagate_emission_gkwh, {"value_col": "THC_g_kWh", "conc_col_mean": "THC_mean_of_windows", "conc_prefix": "THC_ppm"}),
}


def _add_if_missing(df: pd.DataFrame, col: str, series: pd.Series) -> None:
    """Grava a série em `df[col]` se a coluna ainda não existir ou estiver toda NaN."""
    if col not in df.columns:
        df[col] = series
        return
    existing = pd.to_numeric(df[col], errors="coerce")
    if existing.notna().sum() == 0:
        df[col] = series


def _combine_uc_if_missing(df: pd.DataFrame, key: str) -> None:
    """Se `uc_<key>` não existe ou está vazio, compute a partir de uA/uB."""
    uc_col = f"uc_{key}"
    uA = pd.to_numeric(df.get(f"uA_{key}", pd.NA), errors="coerce")
    uB = pd.to_numeric(df.get(f"uB_{key}", pd.NA), errors="coerce")
    uc_calc = np.sqrt(uA.fillna(0.0) ** 2 + uB.fillna(0.0) ** 2).where(
        uA.notna() | uB.notna(), pd.NA
    )
    _add_if_missing(df, uc_col, uc_calc)


def _expand_U_if_missing(df: pd.DataFrame, key: str, k: float = 2.0) -> None:
    """Se `U_<key>` não existe, compute como k·uc."""
    U_col = f"U_{key}"
    uc = pd.to_numeric(df.get(f"uc_{key}", pd.NA), errors="coerce")
    _add_if_missing(df, U_col, k * uc)


def _process_measured(
    df: pd.DataFrame,
    spec: MeasurandSpec,
    instruments: List[Dict[str, Any]],
) -> None:
    """Para grandeza medida: decompõe uB existente em uB_res + uB_acc, calcula %contrib."""
    if spec.value_col not in df.columns:
        return

    # Decompor uB apenas quando a grandeza tem instrumento direto (unidade casa).
    if spec.instrument_key:
        value = pd.to_numeric(df[spec.value_col], errors="coerce")
        uB_res, uB_acc = decompose_uB(value, spec.instrument_key, instruments)
        df[f"uB_res_{spec.key}"] = uB_res
        df[f"uB_acc_{spec.key}"] = uB_acc

    uA = pd.to_numeric(df.get(f"uA_{spec.key}", pd.NA), errors="coerce")
    uc = pd.to_numeric(df.get(f"uc_{spec.key}", pd.NA), errors="coerce")
    if uc.isna().all():
        _combine_uc_if_missing(df, spec.key)
        uc = pd.to_numeric(df.get(f"uc_{spec.key}", pd.NA), errors="coerce")
    _expand_U_if_missing(df, spec.key)

    pct_uA = contribution_var(uA, uc)
    df[f"pct_uA_contrib_{spec.key}"] = pct_uA
    df[f"pct_uB_contrib_{spec.key}"] = (100.0 - pct_uA).where(pct_uA.notna(), pd.NA)


def _process_derived(
    df: pd.DataFrame,
    spec: MeasurandSpec,
) -> None:
    """Para derivada: propaga uA/uB nativamente se faltar; calcula %contrib."""
    propagator_entry = _DERIVED_PROPAGATORS.get(spec.key)
    if propagator_entry is None:
        return
    propagator, kwargs = propagator_entry

    new_cols = propagator(df, **kwargs)
    for col, series in new_cols.items():
        _add_if_missing(df, col, series)

    _combine_uc_if_missing(df, spec.key)
    _expand_U_if_missing(df, spec.key)

    # %contrib usa uA/uB do próprio key (pode ser a versão _pct se a derivada for percentual)
    uA = pd.to_numeric(df.get(f"uA_{spec.key}", pd.NA), errors="coerce")
    uc = pd.to_numeric(df.get(f"uc_{spec.key}", pd.NA), errors="coerce")
    pct_uA = contribution_var(uA, uc)
    df[f"pct_uA_contrib_{spec.key}"] = pct_uA
    df[f"pct_uB_contrib_{spec.key}"] = (100.0 - pct_uA).where(pct_uA.notna(), pd.NA)


def enrich_final_table_with_audit(
    final_table: pd.DataFrame,
    *,
    instruments: List[Dict[str, Any]],
) -> pd.DataFrame:
    """Enriquece o `final_table` in-place (também retorna) com colunas de auditoria.

    `instruments` é o `ConfigBundle.instruments` (List[Dict]), não um DataFrame.
    """
    if final_table is None or final_table.empty:
        return final_table

    df = final_table  # mutate in place
    for spec in AUDITED_MEASURANDS:
        try:
            if spec.kind == "measured":
                _process_measured(df, spec, instruments)
            elif spec.kind == "derived":
                _process_derived(df, spec)
        except Exception as exc:
            print(f"[WARN] uncertainty_audit | '{spec.key}' falhou: {type(exc).__name__}: {exc}")
    df = df.copy()
    return df
