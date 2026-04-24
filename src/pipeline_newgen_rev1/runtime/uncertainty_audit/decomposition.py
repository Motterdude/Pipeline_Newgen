"""Decomposição de uB em componente de resolução e componente de acurácia.

Reproduz `uB_from_instruments_rev2` do legado (nanum_pipeline_29.py:4880-4933) mas
**separa** os 2 termos em vez de combiná-los num único uB.

- `uB_res` = RSS de `resolution_i / √12` para cada componente i do instrumento.
- `uB_acc` = RSS de `limit_i / fator_dist_i`, onde:
    limit_i = |x| · acc_pct + acc_abs + |digits| · |lsd|
    fator_dist = √3  se dist="rect" (default),  1  se dist="normal"

Cada `instrument_key` pode ter múltiplos componentes (múltiplas entradas em `instruments`
com a mesma key) — essas entradas são somadas em quadratura dentro de cada termo (RSS).

O uB total combinado é `√(uB_res² + uB_acc²)`, idêntico ao `uB_from_instruments_rev2` do legado.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


SQRT_3 = math.sqrt(3.0)
SQRT_12 = math.sqrt(12.0)


def _to_float(x: object, default: float = 0.0) -> float:
    if x is None:
        return default
    try:
        if pd.isna(x):
            return default
    except Exception:
        pass
    if isinstance(x, (int, float)):
        try:
            return float(x)
        except Exception:
            return default
    s = str(x).replace("﻿", "").strip()
    if s == "" or s.lower() == "nan":
        return default
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return default


def _rows_for_key(instruments: List[Dict[str, Any]], key_norm: str) -> List[Dict[str, Any]]:
    """Filtra as entradas de `instruments` (List[Dict] do ConfigBundle) pela chave canônica."""
    if not instruments:
        return []
    key = key_norm.strip().lower()
    result: List[Dict[str, Any]] = []
    for row in instruments:
        row_key = str(row.get("key", "")).strip().lower()
        if row_key == key:
            result.append(row)
    return result


def _component_uB(
    value: pd.Series,
    row: Dict[str, Any],
) -> Tuple[pd.Series, pd.Series]:
    """Para uma linha (componente) do instrumento, retorna (u_res_i, u_acc_i) por amostra.

    u_res_i = resolution / √12         (sempre rect)
    u_acc_i = (acc_abs + acc_pct·|x| + digits·lsd) / (√3 se rect, 1 se normal)
    """
    dist = str(row.get("dist", "rect")).strip().lower() or "rect"

    # Range gating: se o instrumento tem range_min/max, a amostra só vê esse componente
    # quando estiver dentro do range.
    rmin_v = _to_float(row.get("range_min"), default=np.nan)
    rmax_v = _to_float(row.get("range_max"), default=np.nan)
    mask = pd.Series(True, index=value.index)
    xv_abs = value.abs()
    if np.isfinite(rmin_v):
        mask = mask & (value >= rmin_v)
    if np.isfinite(rmax_v):
        mask = mask & (value <= rmax_v)

    acc_abs = _to_float(row.get("acc_abs"), 0.0)
    acc_pct = _to_float(row.get("acc_pct"), 0.0)
    digits = _to_float(row.get("digits"), 0.0)
    lsd = _to_float(row.get("lsd"), 0.0)
    resolution = _to_float(row.get("resolution"), 0.0)

    limit = xv_abs * acc_pct + acc_abs + abs(digits) * abs(lsd)
    limit = limit.where(mask, 0.0)

    if dist == "normal":
        u_acc = limit
    else:
        u_acc = limit / SQRT_3

    u_res_scalar = abs(resolution) / SQRT_12 if abs(resolution) > 0 else 0.0
    u_res = pd.Series(u_res_scalar, index=value.index)
    # Aplicar range mask também ao termo de resolução: fora do range não conta.
    u_res = u_res.where(mask, 0.0)

    return u_res, u_acc


def decompose_uB(
    value: pd.Series,
    instrument_key: str,
    instruments: List[Dict[str, Any]],
) -> Tuple[pd.Series, pd.Series]:
    """Dado o valor medido e a chave do instrumento, retorna (uB_res, uB_acc) por amostra.

    RSS entre componentes: se o instrumento tem N linhas em `instruments` com a mesma key,
    uB_res² é a soma das u_res² de cada componente; idem para uB_acc².
    """
    xv = pd.to_numeric(value, errors="coerce")
    if not instrument_key:
        empty = pd.Series(np.nan, index=xv.index, dtype="float64")
        return empty, empty

    rows = _rows_for_key(instruments, instrument_key)
    if not rows:
        empty = pd.Series(np.nan, index=xv.index, dtype="float64")
        return empty, empty

    u_res_sq = pd.Series(0.0, index=xv.index, dtype="float64")
    u_acc_sq = pd.Series(0.0, index=xv.index, dtype="float64")
    for row in rows:
        u_res_i, u_acc_i = _component_uB(xv, row)
        u_res_sq = u_res_sq + pd.to_numeric(u_res_i, errors="coerce").fillna(0.0) ** 2
        u_acc_sq = u_acc_sq + pd.to_numeric(u_acc_i, errors="coerce").fillna(0.0) ** 2

    uB_res = np.sqrt(u_res_sq).where(xv.notna(), pd.NA)
    uB_acc = np.sqrt(u_acc_sq).where(xv.notna(), pd.NA)
    return uB_res, uB_acc
