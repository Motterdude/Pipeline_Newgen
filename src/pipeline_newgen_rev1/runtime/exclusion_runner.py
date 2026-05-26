"""Exclusion list support for pipeline runs.

Loads an exported exclusion list JSON (produced by the Preview Plot exclusion
system) and applies it to the ``ponto`` DataFrame **before** KPI derivation,
so excluded (series, load_kw) pairs are omitted from all downstream mean
calculations and the final ``lv_kpis_clean.xlsx``.

Matching strategy
-----------------
Primary key: ``(basename, round(load_kw, 6))`` — ``basename`` is the exact
value of ``BaseName`` in the raw LabVIEW DataFrame, which is stored in the
exclusion entry when the user excludes a point in the Preview Plot.  This is
the most reliable identifier because it does not depend on display-label
derivation.

y_col is intentionally ignored during pipeline filtering: exclusions apply to
the data row itself, regardless of which metric was being viewed when the
exclusion was created.  [SERIE] entries (y_col="*") and single-metric entries
are both applied — a bad measurement row should not appear in any KPI.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Set, Tuple

import pandas as pd


def load_exclusion_list(path: Path) -> List[dict]:
    """Load exclusion entries from a JSON file.

    Accepts both the raw ``point_exclusions.json`` format (version 1/2) and
    the exported format (includes ``type: exclusion_list``).  Returns an empty
    list if the file is missing, unreadable, or malformed.
    """
    if not path or not Path(path).exists():
        return []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return []
        return [e for e in data.get("exclusions", []) if isinstance(e, dict)]
    except (json.JSONDecodeError, OSError):
        return []


def build_excluded_basename_set(exclusions: List[dict]) -> Set[Tuple[str, float]]:
    """Return a set of (basename, round(load_kw, 6)) pairs to exclude."""
    result: Set[Tuple[str, float]] = set()
    for exc in exclusions:
        bn = str(exc.get("basename", "")).strip()
        if not bn:
            continue
        try:
            lkw = round(float(exc["load_kw"]), 6)
        except (KeyError, TypeError, ValueError):
            continue
        result.add((bn, lkw))
    return result


def apply_exclusions_to_ponto(
    ponto: pd.DataFrame,
    exclusions: List[dict],
) -> Tuple[pd.DataFrame, int]:
    """Filter the ponto DataFrame, removing rows that match the exclusion list.

    Returns ``(filtered_df, n_removed)``.  Never raises — if required columns
    are missing or the exclusion list is empty, returns the DataFrame unchanged.
    """
    if not exclusions or ponto is None or ponto.empty:
        return ponto, 0
    if "BaseName" not in ponto.columns or "Load_kW" not in ponto.columns:
        return ponto, 0

    excluded = build_excluded_basename_set(exclusions)
    if not excluded:
        return ponto, 0

    load_rounded = pd.to_numeric(ponto["Load_kW"], errors="coerce").round(6)
    mask = pd.Series(
        [(str(bn), lkw) not in excluded
         for bn, lkw in zip(ponto["BaseName"].astype(str), load_rounded)],
        index=ponto.index,
    )
    filtered = ponto.loc[mask].copy()
    return filtered, len(ponto) - len(filtered)


def scan_exclusion_lists(directory: Path) -> List[Path]:
    """Return all valid exclusion list JSON files found in *directory*.

    A file qualifies if it contains a non-empty ``"exclusions"`` list and a
    ``"version"`` key (both the raw point_exclusions.json format and the
    exported format produced by the Preview Plot Export button).
    """
    results: List[Path] = []
    if not directory or not Path(directory).is_dir():
        return results
    for f in sorted(Path(directory).glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if (isinstance(data, dict)
                    and "version" in data
                    and isinstance(data.get("exclusions"), list)
                    and len(data["exclusions"]) > 0):
                results.append(f)
        except (json.JSONDecodeError, OSError):
            continue
    return results
