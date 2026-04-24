from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

from .input_discovery import InputFileMeta, discover_input_file


PREFERRED_LABVIEW_SHEET_NAME = "labview"
SAMPLES_PER_WINDOW = 30
INVALID_PRESSURE_SENTINEL = -1000.0


@dataclass(frozen=True)
class LabviewReadResult:
    meta: InputFileMeta
    sheet_name: str
    columns: List[str]
    rows: List[Dict[str, object]]
    pressure_sentinel_hits: Dict[str, int]
    inferred_load_values: List[float]
    inferred_single_load_kw: Optional[float]
    load_source: str


def _excel_engine_candidates() -> List[str]:
    candidates: List[str] = []
    if importlib.util.find_spec("python_calamine") is not None:
        candidates.append("calamine")
    if importlib.util.find_spec("openpyxl") is not None:
        candidates.append("openpyxl")
    return candidates


def _require_excel_engine() -> None:
    if not _excel_engine_candidates():
        raise RuntimeError(
            "An Excel engine is required to read LabVIEW files. Install 'python-calamine' or the optional 'excel' dependency."
        )


def _open_excel_file(path: Path) -> pd.ExcelFile:
    _require_excel_engine()
    last_error: Optional[Exception] = None
    for engine in _excel_engine_candidates():
        try:
            return pd.ExcelFile(path, engine=engine)
        except Exception as exc:
            last_error = exc
            if engine == "calamine":
                print(f"[WARN] ExcelFile calamine falhou em {Path(path).name}: {exc}. Tentando openpyxl...")
    raise RuntimeError(f"Could not open Excel workbook {Path(path).name}: {last_error}")


def _read_excel_sheet(path: Path, *, sheet_name: str | int) -> pd.DataFrame:
    _require_excel_engine()
    last_error: Optional[Exception] = None
    for engine in _excel_engine_candidates():
        try:
            return pd.read_excel(path, sheet_name=sheet_name, engine=engine)
        except Exception as exc:
            last_error = exc
            if engine == "calamine":
                print(f"[WARN] read_excel calamine falhou em {Path(path).name} (sheet={sheet_name}): {exc}. Tentando openpyxl...")
    raise RuntimeError(f"Could not read worksheet {sheet_name!r} in {Path(path).name}: {last_error}")


def _normalize_column_name(value: object) -> str:
    return str(value).replace("\ufeff", "").strip()


def _normalize_columns(values: Sequence[object]) -> List[str]:
    return [_normalize_column_name(value) for value in values]


def _is_unnamed_column(name: object) -> bool:
    return _normalize_column_name(name).startswith("Unnamed")


def _find_first_col_by_substrings(columns: Sequence[str], tokens: Sequence[str]) -> str:
    wanted = [token.lower() for token in tokens]
    for column in columns:
        normalized = _normalize_column_name(column).lower()
        if all(token in normalized for token in wanted):
            return column
    return ""


def _to_float_or_none(value: object) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def list_sheet_names_xlsx(path: Path) -> List[str]:
    workbook = _open_excel_file(Path(path))
    return list(workbook.sheet_names)


def choose_labview_sheet(path: Path) -> str:
    sheets = list_sheet_names_xlsx(path)
    if not sheets:
        raise ValueError(f"No worksheet found in {Path(path).name}.")
    for sheet_name in sheets:
        if sheet_name.strip().lower() == PREFERRED_LABVIEW_SHEET_NAME:
            return sheet_name
    for sheet_name in sheets:
        if PREFERRED_LABVIEW_SHEET_NAME in sheet_name.strip().lower():
            return sheet_name
    if len(sheets) == 1:
        return sheets[0]
    raise ValueError(
        f"Could not choose the LabVIEW worksheet in {Path(path).name}. "
        f"Expected '{PREFERRED_LABVIEW_SHEET_NAME}' or a single sheet, got: {sheets}."
    )


def _quantize_load_kw(value: float) -> float:
    return round(value * 2.0) / 2.0


def _infer_load_values(rows: Sequence[Dict[str, object]], columns: Sequence[str]) -> List[float]:
    load_col = "Carga (kW)" if "Carga (kW)" in columns else _find_first_col_by_substrings(columns, ("carga", "kw"))
    if not load_col:
        return []
    values: List[float] = []
    for row in rows:
        parsed = _to_float_or_none(row.get(load_col))
        if parsed is None:
            continue
        quantized = _quantize_load_kw(parsed)
        if quantized not in values:
            values.append(quantized)
    values.sort()
    return values


def _build_labview_rows(meta: InputFileMeta, raw_rows: Sequence[Dict[str, object]], columns: Sequence[str]) -> Tuple[List[Dict[str, object]], Dict[str, int]]:
    pressure_hits: Dict[str, int] = {}
    rows: List[Dict[str, object]] = []
    inferred_values = _infer_load_values(raw_rows, columns)
    inferred_single = inferred_values[0] if len(inferred_values) == 1 else None

    for index, raw_row in enumerate(raw_rows):
        row = dict(raw_row)
        for column in columns:
            if not str(column).startswith("P_"):
                continue
            parsed = _to_float_or_none(row.get(column))
            if parsed != INVALID_PRESSURE_SENTINEL:
                continue
            row[column] = None
            pressure_hits[column] = pressure_hits.get(column, 0) + 1

        load_signal = _to_float_or_none(row.get("Carga (kW)"))
        if load_signal is None:
            fallback_col = _find_first_col_by_substrings(columns, ("carga", "kw"))
            load_signal = _to_float_or_none(row.get(fallback_col)) if fallback_col else None
        if load_signal is not None:
            load_signal = _quantize_load_kw(load_signal)

        load_kw = meta.load_kw
        if load_kw is None or meta.load_parse == "ambiguous_filename":
            load_kw = load_signal if load_signal is not None else inferred_single

        row["BaseName"] = meta.basename
        row["Load_kW"] = load_kw
        row["Load_Signal_kW"] = load_signal
        row["DIES_pct"] = meta.dies_pct
        row["BIOD_pct"] = meta.biod_pct
        row["EtOH_pct"] = meta.etoh_pct
        row["H2O_pct"] = meta.h2o_pct
        row["Sweep_Key"] = meta.sweep_key
        row["Sweep_Value"] = meta.sweep_value
        row["Sweep_Display_Label"] = meta.sweep_label or None
        row["Index"] = index
        row["WindowID"] = index // SAMPLES_PER_WINDOW
        rows.append(row)
    return rows, pressure_hits


def read_labview_xlsx(path: Path, *, process_root: Optional[Path] = None, meta: Optional[InputFileMeta] = None) -> LabviewReadResult:
    source_path = Path(path).expanduser().resolve()
    roots = (process_root.resolve(),) if process_root is not None else ()
    file_meta = meta if meta is not None else discover_input_file(source_path, roots=roots)
    if file_meta.source_type != "LABVIEW":
        raise ValueError(f"LabVIEW reader expects an .xlsx runtime input, got source_type={file_meta.source_type} for {source_path.name}.")

    sheet_name = choose_labview_sheet(source_path)
    frame = _read_excel_sheet(source_path, sheet_name=sheet_name)
    if frame is None or frame.empty:
        raise ValueError(f"Worksheet '{sheet_name}' in {source_path.name} is empty.")
    frame.columns = _normalize_columns(list(frame.columns))
    frame = frame.loc[:, ~pd.Series(frame.columns).astype(str).str.startswith("Unnamed").values].copy()
    columns = list(frame.columns)
    raw_rows = frame.to_dict(orient="records")

    rows, pressure_hits = _build_labview_rows(file_meta, raw_rows, columns)
    inferred_load_values = _infer_load_values(raw_rows, columns)
    inferred_single_load_kw = inferred_load_values[0] if len(inferred_load_values) == 1 else None
    load_source = "filename"
    if file_meta.load_kw is None:
        load_source = "signal" if inferred_single_load_kw is not None else "missing"
    elif file_meta.load_parse == "ambiguous_filename":
        load_source = "signal" if inferred_single_load_kw is not None else "ambiguous_filename"

    leading_columns = [
        "BaseName",
        "Load_kW",
        "Load_Signal_kW",
        "DIES_pct",
        "BIOD_pct",
        "EtOH_pct",
        "H2O_pct",
        "Sweep_Key",
        "Sweep_Value",
        "Sweep_Display_Label",
        "Index",
        "WindowID",
    ]
    ordered_columns = leading_columns + [column for column in columns if column not in leading_columns]
    return LabviewReadResult(
        meta=file_meta,
        sheet_name=sheet_name,
        columns=ordered_columns,
        rows=rows,
        pressure_sentinel_hits=pressure_hits,
        inferred_load_values=inferred_load_values,
        inferred_single_load_kw=inferred_single_load_kw,
        load_source=load_source,
    )


def summarize_labview_read(result: LabviewReadResult) -> Dict[str, object]:
    return {
        "path": str(result.meta.path),
        "basename": result.meta.basename,
        "sheet_name": result.sheet_name,
        "row_count": len(result.rows),
        "column_count": len(result.columns),
        "columns": result.columns,
        "source_type": result.meta.source_type,
        "load_kw": result.meta.load_kw,
        "load_source": result.load_source,
        "inferred_load_values": result.inferred_load_values,
        "inferred_single_load_kw": result.inferred_single_load_kw,
        "pressure_sentinel_hits": result.pressure_sentinel_hits,
        "sweep_key": result.meta.sweep_key,
        "sweep_value": result.meta.sweep_value,
    }
