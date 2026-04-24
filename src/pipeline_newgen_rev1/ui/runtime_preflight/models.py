from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from .constants import DEFAULT_SWEEP_BIN_TOL, DEFAULT_SWEEP_KEY, SWEEP_VALUE_COL


@dataclass(frozen=True)
class RuntimeSelection:
    aggregation_mode: str
    sweep_key: str = DEFAULT_SWEEP_KEY
    sweep_x_col: str = SWEEP_VALUE_COL
    sweep_bin_tol: float = DEFAULT_SWEEP_BIN_TOL


@dataclass(frozen=True)
class OpenConversionStatus:
    open_files: List[Path]
    missing_csv_opens: List[Path]
    existing_csv_count: int


@dataclass(frozen=True)
class RuntimeInputInventory:
    candidate_paths: List[Path]
    lv_count: int
    kibox_csv_count: int
    motec_csv_count: int


@dataclass(frozen=True)
class RuntimePreflightSnapshot:
    process_dir: Path
    inventory: RuntimeInputInventory
    conversion_status: OpenConversionStatus
    available_sweep_keys: List[str]

