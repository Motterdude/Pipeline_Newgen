"""Left-join logic for merging ponto with fuel_properties / kibox / motec frames."""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

from ._helpers import _canon_name
from .constants import COMPOSITION_COLS


def _normalized_composition_keys(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.index
    out = pd.DataFrame(index=idx)
    dies = pd.to_numeric(df.get("DIES_pct", pd.Series(pd.NA, index=idx)), errors="coerce")
    biod = pd.to_numeric(df.get("BIOD_pct", pd.Series(pd.NA, index=idx)), errors="coerce")
    etoh = pd.to_numeric(df.get("EtOH_pct", pd.Series(pd.NA, index=idx)), errors="coerce")
    h2o = pd.to_numeric(df.get("H2O_pct", pd.Series(pd.NA, index=idx)), errors="coerce")
    has_diesel = dies.notna() | biod.notna()
    has_ethanol = etoh.notna() | h2o.notna()
    out["DIES_pct"] = dies.where(has_diesel, np.where(has_ethanol, 0.0, np.nan))
    out["BIOD_pct"] = biod.where(has_diesel, np.where(has_ethanol, 0.0, np.nan))
    out["EtOH_pct"] = etoh.where(has_ethanol, np.where(has_diesel, 0.0, np.nan))
    out["H2O_pct"] = h2o.where(has_ethanol, np.where(has_diesel, 0.0, np.nan))
    return out


def _normalized_extra_merge_key(df: pd.DataFrame, col: str) -> pd.Series:
    idx = df.index
    raw = df.get(col, pd.Series(pd.NA, index=idx))
    numeric = pd.to_numeric(raw, errors="coerce")
    if numeric.notna().any():
        return numeric
    return raw.map(_canon_name)


def _left_merge_on_fuel_keys(left: pd.DataFrame, right: pd.DataFrame, extra_on: Optional[List[str]] = None) -> pd.DataFrame:
    extra = extra_on or []
    l = left.copy()
    r = right.copy()
    l_norm = _normalized_composition_keys(l)
    r_norm = _normalized_composition_keys(r)
    merge_cols: List[str] = []
    for c in extra + COMPOSITION_COLS:
        tmp = f"__merge_{c}"
        if c in extra:
            l[tmp] = _normalized_extra_merge_key(l, c)
            r[tmp] = _normalized_extra_merge_key(r, c)
        else:
            l[tmp] = pd.to_numeric(l_norm[c], errors="coerce")
            r[tmp] = pd.to_numeric(r_norm[c], errors="coerce")
        merge_cols.append(tmp)
    right_payload = r.drop(columns=[c for c in extra + COMPOSITION_COLS if c in r.columns]).copy()
    for tmp in merge_cols:
        right_payload[tmp] = r[tmp]
    out = l.merge(right_payload, on=merge_cols, how="left")
    out.drop(columns=merge_cols, inplace=True)
    return out


def _find_kibox_col_by_tokens(df: pd.DataFrame, tokens: List[str]) -> Optional[str]:
    want = [str(t).lower().replace("_", "").replace(" ", "") for t in tokens if str(t).strip()]
    if not want:
        return None
    for c in df.columns:
        cs = str(c)
        if not cs.startswith("KIBOX_"):
            continue
        canon = cs.lower().replace("_", "").replace(" ", "")
        if all(w in canon for w in want):
            return c
    return None
