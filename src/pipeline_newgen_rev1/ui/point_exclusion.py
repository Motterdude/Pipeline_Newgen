"""Point exclusion system: interactive outlier removal with engineering justification.

Key design (v3):
  - Exclusions are GLOBAL: once a point is excluded, it disappears from ALL plots.
  - ExclusionKey = (series_label, load_kw_rounded) — y_col is metadata only.
  - y_col in the JSON records which plot the user was viewing when they excluded the point,
    but it does NOT limit which plots the exclusion applies to.
  - Series exclusions (reason starts with "[SERIE]") exclude all load_kw values for that series.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Set, Tuple

import pandas as pd

ExclusionKey = Tuple[str, float]


@dataclass
class PointExclusion:
    series_label: str
    load_kw: float
    y_col: str
    basename: str
    reason: str
    excluded_at: str
    excluded_by: str = "user"

    @property
    def key(self) -> ExclusionKey:
        return (self.series_label, round(self.load_kw, 6))


class ExclusionStore:
    """Manages point exclusions with JSON persistence."""

    def __init__(self, storage_path: Path):
        self._path = storage_path
        self._exclusions: List[PointExclusion] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
            seen_keys: Set[ExclusionKey] = set()
            for entry in data.get("exclusions", []):
                if not isinstance(entry, dict):
                    continue
                try:
                    exc = PointExclusion(
                        series_label=str(entry.get("series_label", "")),
                        load_kw=float(entry.get("load_kw", 0)),
                        y_col=str(entry.get("y_col", "*")),
                        basename=str(entry.get("basename", "")),
                        reason=str(entry.get("reason", "")),
                        excluded_at=str(entry.get("excluded_at", "")),
                        excluded_by=str(entry.get("excluded_by", "user")),
                    )
                    if exc.key not in seen_keys:
                        self._exclusions.append(exc)
                        seen_keys.add(exc.key)
                except (TypeError, ValueError):
                    continue
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 3,
            "exclusions": [asdict(e) for e in self._exclusions],
        }
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def add(self, exclusion: PointExclusion) -> None:
        if exclusion.key not in {e.key for e in self._exclusions}:
            self._exclusions.append(exclusion)
            self._save()

    def add_batch(self, exclusions: List[PointExclusion]) -> None:
        existing_keys = {e.key for e in self._exclusions}
        added = False
        for exc in exclusions:
            if exc.key not in existing_keys:
                self._exclusions.append(exc)
                existing_keys.add(exc.key)
                added = True
        if added:
            self._save()

    def remove(self, key: ExclusionKey) -> None:
        self._exclusions = [e for e in self._exclusions if e.key != key]
        self._save()

    def remove_series(self, series_label: str) -> None:
        self._exclusions = [e for e in self._exclusions if e.series_label != series_label]
        self._save()

    def remove_all(self) -> None:
        self._exclusions = []
        self._save()

    def active_keys(self) -> Set[ExclusionKey]:
        return {e.key for e in self._exclusions}

    def active_keys_for_ycol(self, y_col: str) -> Set[Tuple[str, float]]:
        """Backward compat — returns all keys (global behavior)."""
        return self.active_keys()

    def is_excluded(self, series_label: str, load_kw: float, y_col: str = "") -> bool:
        return (series_label, round(load_kw, 6)) in self.active_keys()

    def all_exclusions(self) -> List[PointExclusion]:
        return list(self._exclusions)

    def series_exclusions(self) -> List[PointExclusion]:
        """Exclusions that represent full-series removals."""
        seen: Set[str] = set()
        result: List[PointExclusion] = []
        for e in self._exclusions:
            if e.reason.startswith("[SERIE]") and e.series_label not in seen:
                result.append(e)
                seen.add(e.series_label)
        return result

    def point_exclusions(self) -> List[PointExclusion]:
        """Exclusions that are individual points (not part of a series exclusion)."""
        series_labels = {e.series_label for e in self._exclusions if e.reason.startswith("[SERIE]")}
        return [e for e in self._exclusions if e.series_label not in series_labels]

    def series_point_count(self, series_label: str) -> int:
        return sum(1 for e in self._exclusions if e.series_label == series_label)

    def series_points(self, series_label: str) -> List[PointExclusion]:
        return [e for e in self._exclusions if e.series_label == series_label]

    def count(self) -> int:
        return len(self._exclusions)


def apply_exclusions(
    df: pd.DataFrame,
    store: ExclusionStore,
    series_labels: pd.Series,
    x_col: str = "Load_kW",
    y_col: str = "",
) -> pd.DataFrame:
    """Filter out ALL excluded points globally. Returns a copy.

    The y_col parameter is accepted for API compatibility but ignored —
    all exclusions apply to all plots.
    """
    keys = store.active_keys()
    if not keys:
        return df

    load_rounded = pd.to_numeric(df[x_col], errors="coerce").round(6)
    pair_series = list(zip(series_labels, load_rounded))

    mask = pd.Series(
        [(lbl, lkw) not in keys for lbl, lkw in pair_series],
        index=df.index,
    )
    return df.loc[mask].copy()
