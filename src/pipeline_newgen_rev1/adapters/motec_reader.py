from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .input_discovery import InputFileMeta, discover_input_file


SAMPLES_PER_WINDOW = 30
MOTEC_HEADER_ROWS = 14


@dataclass(frozen=True)
class MotecReadResult:
    meta: InputFileMeta
    delimiter: str
    metadata: Dict[str, float]
    columns: List[str]
    rows: List[Dict[str, object]]


def _normalize_text(value: object) -> str:
    return str(value).replace("\ufeff", "").strip()


def _normalize_key(value: object) -> str:
    return _normalize_text(value).lower()


def _to_float_or_none(value: object) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def _sniff_delimiter(sample: str) -> str:
    candidates = [",", ";", "\t"]
    counts = {candidate: sample.count(candidate) for candidate in candidates}
    return max(candidates, key=lambda candidate: counts[candidate])


def _read_text_with_fallback(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="ignore")


def _normalize_columns(values: Sequence[object]) -> List[str]:
    return [_normalize_text(value) for value in values]


def _read_motec_metadata(lines: Sequence[str], *, delimiter: str) -> Dict[str, float]:
    metadata: Dict[str, float] = {}
    reader = csv.reader(lines[:MOTEC_HEADER_ROWS], delimiter=delimiter)
    for row in reader:
        if not row:
            continue
        key = _normalize_key(row[0].strip('"'))
        if key == "sample rate" and len(row) > 1:
            metadata["Motec_SampleRate_Hz"] = _to_float_or_none(row[1]) or 0.0
        elif key == "duration" and len(row) > 1:
            metadata["Motec_Duration_s"] = _to_float_or_none(row[1]) or 0.0
    return metadata


def _build_motec_rows(meta: InputFileMeta, header: Sequence[str], data_rows: Sequence[Sequence[object]], metadata: Dict[str, float]) -> List[Dict[str, object]]:
    clean_header = _normalize_columns(header)
    motec_columns: List[str] = []
    for index, column in enumerate(clean_header):
        name = column if column else f"Col_{index + 1}"
        motec_columns.append(f"Motec_{name}")

    rows: List[Dict[str, object]] = []
    previous_time: Optional[float] = None
    time_column = next((column for column in motec_columns if _normalize_key(column) == _normalize_key("Motec_Time")), "")

    for index, raw_values in enumerate(data_rows):
        row = {
            motec_columns[pos]: (raw_values[pos] if pos < len(raw_values) else None)
            for pos in range(len(motec_columns))
        }
        for key, value in metadata.items():
            row[key] = value

        current_time = _to_float_or_none(row.get(time_column)) if time_column else None
        row["Motec_Time_Delta_s"] = None if current_time is None or previous_time is None else current_time - previous_time
        if current_time is not None:
            previous_time = current_time

        row["BaseName"] = meta.basename
        row["Load_kW"] = meta.load_kw
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
    return rows


def read_motec_csv(path: Path, *, process_root: Optional[Path] = None, meta: Optional[InputFileMeta] = None) -> MotecReadResult:
    source_path = Path(path).expanduser().resolve()
    roots = (process_root.resolve(),) if process_root is not None else ()
    file_meta = meta if meta is not None else discover_input_file(source_path, roots=roots)
    if file_meta.source_type != "MOTEC":
        raise ValueError(f"MoTeC reader expects a _m.csv runtime input, got source_type={file_meta.source_type} for {source_path.name}.")

    text = _read_text_with_fallback(source_path)
    lines = text.splitlines()
    sample = "\n".join(lines[:20])
    delimiter = _sniff_delimiter(sample)
    metadata = _read_motec_metadata(lines, delimiter=delimiter)

    reader = csv.reader(lines[MOTEC_HEADER_ROWS:], delimiter=delimiter)
    raw_rows = list(reader)
    if not raw_rows:
        raise ValueError(f"MoTeC file has no rows after the header block: {source_path.name}")

    header = raw_rows[0]
    body = raw_rows[1:]
    if not body:
        raise ValueError(f"MoTeC file has no unit/data rows after the header line: {source_path.name}")

    # Row 16 carries the units in the legacy export. Real data starts after that.
    data_rows = body[1:] if len(body) > 1 else []
    if not data_rows:
        raise ValueError(f"MoTeC file has no data rows after dropping the units row: {source_path.name}")

    rows = _build_motec_rows(file_meta, header, data_rows, metadata)
    leading_columns = [
        "BaseName",
        "Load_kW",
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
    dynamic_columns = _normalize_columns(header)
    motec_columns = [f"Motec_{column if column else f'Col_{index + 1}'}" for index, column in enumerate(dynamic_columns)]
    metadata_columns = list(metadata.keys())
    trailing_columns = ["Motec_Time_Delta_s"]
    ordered_columns = leading_columns + motec_columns + metadata_columns + trailing_columns
    return MotecReadResult(
        meta=file_meta,
        delimiter=delimiter,
        metadata=metadata,
        columns=ordered_columns,
        rows=rows,
    )


def summarize_motec_read(result: MotecReadResult) -> Dict[str, object]:
    return {
        "path": str(result.meta.path),
        "basename": result.meta.basename,
        "delimiter": result.delimiter,
        "row_count": len(result.rows),
        "column_count": len(result.columns),
        "columns": result.columns,
        "source_type": result.meta.source_type,
        "load_kw": result.meta.load_kw,
        "metadata": result.metadata,
        "sweep_key": result.meta.sweep_key,
        "sweep_value": result.meta.sweep_value,
    }
