"""Source identity and run-context columns (SourceFolder, Sentido_Carga, Iteracao)."""
from __future__ import annotations

import re
from typing import List

import pandas as pd

from ._helpers import _canon_name


def _basename_parts(basename: object) -> List[str]:
    return [str(p).strip() for p in str(basename).split("__") if str(p).strip()]


def _basename_source_folder_parts(basename: object) -> List[str]:
    parts = _basename_parts(basename)
    if len(parts) <= 1:
        return []
    return parts[:-1]


def _basename_source_folder_display(basename: object) -> str:
    return " / ".join(_basename_source_folder_parts(basename))


def _basename_source_file(basename: object) -> str:
    parts = _basename_parts(basename)
    if not parts:
        return ""
    return parts[-1]


def add_source_identity_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "BaseName" not in df.columns:
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    out = df.copy()
    out["SourceFolder"] = out["BaseName"].map(_basename_source_folder_display)
    out["SourceFile"] = out["BaseName"].map(_basename_source_file)
    return out


def _infer_sentido_carga_from_folder_parts(parts: List[str]) -> object:
    for part in reversed(parts):
        s = _canon_name(part).replace("_", " ").replace("-", " ")
        if "subindo" in s or "subida" in s or re.search(r"\bup\b", s):
            return "subida"
        if "descendo" in s or "descida" in s or re.search(r"\bdown\b", s):
            return "descida"
    return pd.NA


def _infer_iteracao_from_folder_parts(parts: List[str]) -> object:
    for part in reversed(parts):
        m = re.search(r"(\d+)\s*$", str(part))
        if m:
            return int(m.group(1))
    for part in reversed(parts):
        nums = re.findall(r"\d+", str(part))
        if nums:
            return int(nums[-1])
    return pd.NA


def add_run_context_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "BaseName" not in df.columns:
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    out = df.copy()
    folder_parts = out["BaseName"].map(_basename_source_folder_parts)
    out["Sentido_Carga"] = folder_parts.map(_infer_sentido_carga_from_folder_parts)
    out["Iteracao"] = pd.to_numeric(folder_parts.map(_infer_iteracao_from_folder_parts), errors="coerce").astype("Int64")
    return out
