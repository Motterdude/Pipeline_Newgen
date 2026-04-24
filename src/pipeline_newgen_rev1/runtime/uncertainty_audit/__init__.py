"""Audit layer de incerteza: adiciona colunas auditáveis + %contribuição uA/uB."""

from __future__ import annotations

from .contribution import contribution_var
from .core import enrich_final_table_with_audit
from .decomposition import decompose_uB
from .derived_propagation import (
    propagate_bsfc,
    propagate_consumo_L_h,
    propagate_emission_gkwh,
    propagate_n_th,
)
from .specs import AUDITED_MEASURANDS, MeasurandSpec, audited_measurands_by_key


__all__ = [
    "AUDITED_MEASURANDS",
    "MeasurandSpec",
    "audited_measurands_by_key",
    "contribution_var",
    "decompose_uB",
    "enrich_final_table_with_audit",
    "propagate_bsfc",
    "propagate_consumo_L_h",
    "propagate_emission_gkwh",
    "propagate_n_th",
]
