"""Compare-plots grouping: pairs subida x descida from the same campaign.

Unlike compare_iteracoes (which compares baseline vs aditivado across
directions), compare_plots compares subida vs descida *within* a single
campaign.  The actual rendering reuses the unitary_plots dispatch with
``series_col="_COMPARE_SERIES"``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from .final_table._helpers import _canon_name, _is_blank_cell
from .final_table._source_identity import add_source_identity_columns


def _safe_name(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]+", "_", str(name))
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _source_folder_leaf(source_folder: object) -> str:
    s = str(source_folder or "").strip()
    if not s:
        return ""
    parts = [p.strip() for p in s.split("/") if p.strip()]
    return parts[-1] if parts else s


def _normalize_compare_series_name(source_folder: object) -> str:
    leaf = _source_folder_leaf(source_folder)
    if not leaf:
        return "origem_desconhecida"

    s = _canon_name(leaf).replace(" ", "_").replace("-", "_")
    s = re.sub(r"_+", "_", s).strip("_")
    s = re.sub(r"(^|_)subindo(?=_|$)", r"\1subida", s)
    s = re.sub(r"(^|_)descendo(?=_|$)", r"\1descida", s)
    if not s:
        return "origem_desconhecida"
    return s


def _safe_folder_name(name: object) -> str:
    s = str(name or "").strip()
    if not s:
        return "compare"
    s = re.sub(r'[<>:"/\\|?*]', "_", s)
    s = s.strip().rstrip(".")
    return s if s else "compare"


def _infer_source_direction_from_folder_name(source_folder: object) -> Optional[str]:
    s = _canon_name(source_folder).replace("_", " ").replace("-", " ")
    if "subindo" in s or "subida" in s or re.search(r"\bup\b", s):
        return "subindo"
    if "descendo" in s or "descida" in s or re.search(r"\bdown\b", s):
        return "descendo"
    return None


def _compare_group_key_from_source_folder(source_folder: object) -> str:
    s = str(source_folder or "").strip()
    if not s:
        return ""

    parts = [p.strip() for p in s.split("/") if p.strip()]
    clean_parts: List[str] = []
    for part in parts:
        t = _canon_name(part).replace("_", " ").replace("-", " ")
        t = re.sub(r"\b(subindo|subida|descendo|descida|up|down)\b", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            clean_parts.append(t)

    if not clean_parts:
        return ""
    return "__".join(_safe_name(p) for p in clean_parts)


def iter_compare_plot_groups(
    df: pd.DataFrame,
    root: Optional[Path] = None,
) -> List[Tuple[str, Path, pd.DataFrame]]:
    if df is None or df.empty:
        return []

    tmp = add_source_identity_columns(df)
    if "SourceFolder" not in tmp.columns:
        return []

    tmp = tmp.copy()
    tmp["_COMPARE_GROUP"] = tmp["SourceFolder"].map(_compare_group_key_from_source_folder)
    tmp["_COMPARE_SERIES"] = tmp["SourceFolder"].map(_normalize_compare_series_name)
    tmp["_COMPARE_DIRECTION"] = tmp["SourceFolder"].map(_infer_source_direction_from_folder_name)
    tmp["_COMPARE_SERIES"] = tmp["_COMPARE_SERIES"].where(
        tmp["_COMPARE_SERIES"].map(lambda x: not _is_blank_cell(x)),
        "origem_desconhecida",
    )

    base_root = (root or Path(".")) / "compare"
    groups: List[Tuple[str, Path, pd.DataFrame]] = []
    for group_key, d in tmp.groupby("_COMPARE_GROUP", dropna=False, sort=True):
        gk = str(group_key or "").strip()
        if not gk:
            continue

        dirs = set(
            str(x).strip().lower()
            for x in d["_COMPARE_DIRECTION"].dropna().tolist()
            if str(x).strip()
        )
        if "subindo" not in dirs or "descendo" not in dirs:
            continue

        subida_vals = sorted(set(
            str(v).strip()
            for v in d.loc[d["_COMPARE_DIRECTION"].eq("subindo"), "_COMPARE_SERIES"].dropna().tolist()
            if str(v).strip()
        ))
        descida_vals = sorted(set(
            str(v).strip()
            for v in d.loc[d["_COMPARE_DIRECTION"].eq("descendo"), "_COMPARE_SERIES"].dropna().tolist()
            if str(v).strip()
        ))
        if subida_vals and descida_vals:
            compare_name = f"{subida_vals[0]} vs {descida_vals[0]}"
        else:
            uniq = sorted(set(
                str(v).strip()
                for v in d["_COMPARE_SERIES"].dropna().tolist()
                if str(v).strip()
            ))
            compare_name = " vs ".join(uniq[:2]) if uniq else gk

        plot_dir = base_root / _safe_folder_name(compare_name)
        groups.append((gk, plot_dir, d.copy()))

    return groups
