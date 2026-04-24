from __future__ import annotations

from pathlib import Path
from typing import List

from ...adapters.input_discovery import parse_filename_sweep
from ...adapters.open_to_csv import planned_pipeline_csv_path
from .constants import DEFAULT_SWEEP_KEY
from .models import OpenConversionStatus, RuntimeInputInventory
from .normalize import normalize_sweep_key

def scan_open_conversion_status(process_dir: Path) -> OpenConversionStatus:
    open_files = sorted(path for path in Path(process_dir).rglob("*.open") if path.is_file())
    missing_csv_opens = [path for path in open_files if not planned_pipeline_csv_path(path).exists()]
    existing_csv_count = sum(1 for path in open_files if planned_pipeline_csv_path(path).exists())
    return OpenConversionStatus(
        open_files=open_files,
        missing_csv_opens=missing_csv_opens,
        existing_csv_count=existing_csv_count,
    )


def scan_runtime_input_inventory(process_dir: Path) -> RuntimeInputInventory:
    candidate_paths = sorted(
        path
        for pattern in ("*.xlsx", "*.csv", "*.open")
        for path in Path(process_dir).rglob(pattern)
        if path.is_file() and not path.name.startswith("~$")
    )
    lv_count = sum(1 for path in candidate_paths if path.suffix.lower() == ".xlsx")
    kibox_csv_count = sum(1 for path in candidate_paths if path.suffix.lower() == ".csv" and path.stem.lower().endswith("_i"))
    motec_csv_count = sum(1 for path in candidate_paths if path.suffix.lower() == ".csv" and path.stem.lower().endswith("_m"))
    return RuntimeInputInventory(
        candidate_paths=candidate_paths,
        lv_count=lv_count,
        kibox_csv_count=kibox_csv_count,
        motec_csv_count=motec_csv_count,
    )


def available_sweep_keys_from_paths(paths: List[Path]) -> List[str]:
    found: List[str] = []
    for path in paths:
        sweep_key, _sweep_value, _parse_source = parse_filename_sweep(path.stem)
        if not sweep_key:
            continue
        canonical = normalize_sweep_key(sweep_key)
        if canonical not in found:
            found.append(canonical)
    if not found:
        found.append(DEFAULT_SWEEP_KEY)
    return found
