"""Cálculo variance-weighted de %uA_contrib e %uB_contrib (GUM §F.1.2.4).

Para um ponto com componentes uA (Tipo A, aleatória) e uB (Tipo B, sistemática):
    uc² = uA² + uB²
    %uA_contrib_var = 100 · uA² / uc²     (range 0-100)
    %uB_contrib_var = 100 - %uA_contrib_var = 100 · uB² / uc²

Retorno em NaN quando uc é NaN ou zero (ambíguo — sem incerteza para repartir).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def contribution_var(uA: pd.Series, uc: pd.Series) -> pd.Series:
    """%uA_contrib_var = 100·(uA/uc)². Range [0,100]. NaN se uc ausente ou zero."""
    uA_num = pd.to_numeric(uA, errors="coerce")
    uc_num = pd.to_numeric(uc, errors="coerce")
    ratio_sq = np.where(
        (uc_num > 0) & uc_num.notna() & uA_num.notna(),
        (uA_num / uc_num.replace(0, np.nan)) ** 2,
        np.nan,
    )
    return pd.Series(ratio_sq * 100.0, index=uA_num.index, dtype="float64")
