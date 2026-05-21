"""Point exclusion system: interactive outlier removal with engineering justification."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

ExclusionKey = Tuple[str, float]  # (series_label, load_kw_rounded)


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
            for entry in data.get("exclusions", []):
                if isinstance(entry, dict):
                    try:
                        self._exclusions.append(PointExclusion(
                            series_label=str(entry.get("series_label", "")),
                            load_kw=float(entry.get("load_kw", 0)),
                            y_col=str(entry.get("y_col", "")),
                            basename=str(entry.get("basename", "")),
                            reason=str(entry.get("reason", "")),
                            excluded_at=str(entry.get("excluded_at", "")),
                            excluded_by=str(entry.get("excluded_by", "user")),
                        ))
                    except (TypeError, ValueError):
                        continue
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "exclusions": [asdict(e) for e in self._exclusions],
        }
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def add(self, exclusion: PointExclusion) -> None:
        existing_keys = {e.key for e in self._exclusions}
        if exclusion.key not in existing_keys:
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

    def active_keys(self) -> Set[ExclusionKey]:
        return {e.key for e in self._exclusions}

    def is_excluded(self, series_label: str, load_kw: float) -> bool:
        key = (series_label, round(load_kw, 6))
        return key in self.active_keys()

    def all_exclusions(self) -> List[PointExclusion]:
        return list(self._exclusions)

    def count(self) -> int:
        return len(self._exclusions)


def apply_exclusions(
    df: pd.DataFrame,
    store: ExclusionStore,
    series_labels: pd.Series,
    x_col: str = "Load_kW",
) -> pd.DataFrame:
    """Filter out excluded points. Returns a copy — never mutates original."""
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
