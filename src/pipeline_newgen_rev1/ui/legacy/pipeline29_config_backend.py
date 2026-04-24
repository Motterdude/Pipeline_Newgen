from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import pandas as pd

from ...config import (
    ConfigBundle,
    bootstrap_text_config_from_excel as modern_bootstrap_text_config_from_excel,
    default_app_state_dir,
    default_text_config_dir as modern_default_text_config_dir,
    load_text_config_bundle as modern_load_text_config_bundle,
    save_text_config_bundle as modern_save_text_config_bundle,
    text_config_exists,
    validate_bundle as modern_validate_bundle,
)
from ...config.adapter import (
    DEFAULT_COMPARE_COLUMNS,
    DEFAULT_FUEL_PROPERTY_COLUMNS,
    DEFAULT_INSTRUMENT_COLUMNS,
    DEFAULT_PLOT_COLUMNS,
    DEFAULT_REPORTING_COLUMNS,
)


DEFAULT_MAPPING_COLUMNS = ["key", "col_mean", "col_sd", "unit", "notes"]
DEFAULT_COMPARE_SERIES_OPTIONS = [
    "baseline_media",
    "baseline_subida",
    "baseline_descida",
    "aditivado_media",
    "aditivado_subida",
    "aditivado_descida",
]
DEFAULT_COMPARE_METRIC_OPTIONS = ["consumo", "co2", "co", "o2", "nox", "thc"]


@dataclass
class Pipeline29ConfigBundle:
    mappings: Dict[str, Dict[str, str]]
    instruments_df: pd.DataFrame
    reporting_df: pd.DataFrame
    plots_df: pd.DataFrame
    compare_df: pd.DataFrame
    fuel_properties_df: pd.DataFrame
    data_quality_cfg: Dict[str, float]
    defaults_cfg: Dict[str, str]
    source_kind: str = "text"
    source_path: Optional[Path] = None
    text_dir: Optional[Path] = None


def default_text_config_dir(base_dir: Path) -> Path:
    return modern_default_text_config_dir(base_dir)


def default_gui_state_path() -> Path:
    return default_app_state_dir() / "config_gui_state.json"


def default_project_root(project_root: Optional[Path] = None) -> Path:
    if project_root is not None:
        return Path(project_root).expanduser().resolve()
    env_root = os.environ.get("PIPELINE_NEWGEN_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists() and (parent / "src" / "pipeline_newgen_rev1").exists():
            return parent
    return current.parents[4]


def default_preset_dir(project_root: Optional[Path] = None) -> Path:
    return default_project_root(project_root) / "config" / "presets"


def _records_to_dataframe(records: List[Dict[str, Any]], columns: List[str]) -> pd.DataFrame:
    normalized = []
    for record in records:
        row = {column: record.get(column, pd.NA) for column in columns}
        for key, value in record.items():
            if key not in row:
                row[key] = value
        normalized.append(row)
    if not normalized:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame(normalized)
    for column in columns:
        if column not in frame.columns:
            frame[column] = pd.NA
    ordered = columns + [column for column in frame.columns if column not in columns]
    return frame[ordered].copy()


def _dataframe_records(frame: pd.DataFrame, columns: List[str]) -> List[Dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    rows: List[Dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        row = {column: record.get(column, None) for column in columns}
        for key, value in record.items():
            if key not in row:
                row[key] = value
        rows.append(row)
    return rows


def _legacy_to_modern(bundle: Pipeline29ConfigBundle) -> ConfigBundle:
    return ConfigBundle(
        mappings=dict(bundle.mappings),
        instruments=_dataframe_records(bundle.instruments_df, DEFAULT_INSTRUMENT_COLUMNS),
        reporting=_dataframe_records(bundle.reporting_df, DEFAULT_REPORTING_COLUMNS),
        plots=_dataframe_records(bundle.plots_df, DEFAULT_PLOT_COLUMNS),
        compare=_dataframe_records(bundle.compare_df, DEFAULT_COMPARE_COLUMNS),
        fuel_properties=_dataframe_records(bundle.fuel_properties_df, DEFAULT_FUEL_PROPERTY_COLUMNS),
        data_quality=dict(bundle.data_quality_cfg),
        defaults=dict(bundle.defaults_cfg),
        source_kind=bundle.source_kind,
        source_path=bundle.source_path,
        text_dir=bundle.text_dir,
    )


def _modern_to_legacy(bundle: ConfigBundle) -> Pipeline29ConfigBundle:
    return Pipeline29ConfigBundle(
        mappings=dict(bundle.mappings),
        instruments_df=_records_to_dataframe(bundle.instruments, DEFAULT_INSTRUMENT_COLUMNS),
        reporting_df=_records_to_dataframe(bundle.reporting, DEFAULT_REPORTING_COLUMNS),
        plots_df=_records_to_dataframe(bundle.plots, DEFAULT_PLOT_COLUMNS),
        compare_df=_records_to_dataframe(bundle.compare, DEFAULT_COMPARE_COLUMNS),
        fuel_properties_df=_records_to_dataframe(bundle.fuel_properties, DEFAULT_FUEL_PROPERTY_COLUMNS),
        data_quality_cfg=dict(bundle.data_quality),
        defaults_cfg=dict(bundle.defaults),
        source_kind=bundle.source_kind,
        source_path=bundle.source_path,
        text_dir=bundle.text_dir,
    )


def load_text_config_bundle(config_dir: Path) -> Pipeline29ConfigBundle:
    return _modern_to_legacy(modern_load_text_config_bundle(config_dir))


def save_text_config_bundle(bundle: Pipeline29ConfigBundle, config_dir: Path) -> Pipeline29ConfigBundle:
    saved = modern_save_text_config_bundle(_legacy_to_modern(bundle), config_dir)
    return _modern_to_legacy(saved)


def bootstrap_text_config_from_excel(excel_path: Path, config_dir: Path) -> Pipeline29ConfigBundle:
    saved = modern_bootstrap_text_config_from_excel(excel_path, config_dir)
    return _modern_to_legacy(saved)


def validate_bundle(bundle: Pipeline29ConfigBundle) -> List[str]:
    return modern_validate_bundle(_legacy_to_modern(bundle))


def bundle_to_preset_payload(bundle: Pipeline29ConfigBundle) -> Dict[str, Any]:
    modern = _legacy_to_modern(bundle)
    return {
        "mappings": modern.mappings,
        "instruments": modern.instruments,
        "reporting": modern.reporting,
        "plots": modern.plots,
        "compare": modern.compare,
        "fuel_properties": modern.fuel_properties,
        "data_quality": modern.data_quality,
        "defaults": modern.defaults,
    }


def bundle_from_preset_payload(payload: Mapping[str, Any]) -> Pipeline29ConfigBundle:
    return _modern_to_legacy(
        ConfigBundle(
            mappings=dict(payload.get("mappings", {}) or {}),
            instruments=list(payload.get("instruments", []) or []),
            reporting=list(payload.get("reporting", []) or []),
            plots=list(payload.get("plots", []) or []),
            compare=list(payload.get("compare", []) or []),
            fuel_properties=list(payload.get("fuel_properties", []) or []),
            data_quality=dict(payload.get("data_quality", {}) or {}),
            defaults=dict(payload.get("defaults", {}) or {}),
            source_kind="preset",
            source_path=None,
            text_dir=None,
        )
    )


def save_bundle_preset(bundle: Pipeline29ConfigBundle, path: Path) -> None:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(bundle_to_preset_payload(bundle), indent=2, ensure_ascii=True), encoding="utf-8")


def load_bundle_preset(path: Path) -> Pipeline29ConfigBundle:
    target = Path(path).expanduser().resolve()
    payload = json.loads(target.read_text(encoding="utf-8"))
    return bundle_from_preset_payload(payload)


def save_gui_state(payload: Dict[str, Any], path: Optional[Path] = None) -> None:
    target = Path(path).expanduser().resolve() if path is not None else default_gui_state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def load_gui_state(path: Optional[Path] = None) -> Dict[str, Any]:
    target = Path(path).expanduser().resolve() if path is not None else default_gui_state_path()
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
