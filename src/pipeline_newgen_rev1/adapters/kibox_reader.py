from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .input_discovery import InputFileMeta, discover_input_file


@dataclass(frozen=True)
class KiboxReadResult:
    meta: InputFileMeta
    delimiter: str
    header_row: int
    columns: List[str]
    rows: List[Dict[str, object]]


@dataclass(frozen=True)
class KiboxAggregateResult:
    meta: InputFileMeta
    source_columns: List[str]
    kept_columns: List[str]
    aggregate_row: Dict[str, object]


_NUM_REGEX = re.compile(r"[-+]?(\d{1,3}(\.\d{3})+|\d+)([.,]\d+)?")


def _normalize_text(value: object) -> str:
    return str(value).replace("\ufeff", "").strip()


def _sniff_delimiter(sample: str) -> str:
    candidates = [",", ";", "\t", "|"]
    counts = {candidate: sample.count(candidate) for candidate in candidates}
    return max(candidates, key=lambda candidate: counts[candidate])


def _find_header_row(lines: Sequence[str], *, delimiter: str, min_cols: int = 6) -> int:
    best_index = 0
    best_cols = 0
    for index, line in enumerate(lines[:80]):
        columns = line.split(delimiter)
        ncols = len(columns)
        if ncols > best_cols:
            best_cols = ncols
            best_index = index
        if ncols >= min_cols and any(char.isalpha() for char in line):
            return index
    return best_index


def _normalize_columns(values: Sequence[object]) -> List[str]:
    return [_normalize_text(value) for value in values]


def _drop_unnamed_columns(columns: Sequence[str], rows: Sequence[Dict[str, object]]) -> tuple[List[str], List[Dict[str, object]]]:
    keep = [column for column in columns if column and not column.startswith("Unnamed")]
    cleaned_rows = [{column: row.get(column) for column in keep} for row in rows]
    return keep, cleaned_rows


def _coerce_numeric_value(value: object) -> Optional[float]:
    if value is None:
        return None
    text = _normalize_text(value).replace("\u00A0", " ").replace(" ", "")
    if not text:
        return None
    extracted = _NUM_REGEX.search(text)
    if extracted is None:
        return None
    token = extracted.group(0)
    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token and "." not in token:
        token = token.replace(",", ".")
    try:
        return float(token)
    except Exception:
        return None


def _basename_source_folder_display(basename: object) -> str:
    text = _normalize_text(basename)
    if "__" not in text:
        return ""
    return text.split("__", 1)[0]


def read_kibox_csv(path: Path, *, process_root: Optional[Path] = None, meta: Optional[InputFileMeta] = None) -> KiboxReadResult:
    source_path = Path(path).expanduser().resolve()
    roots = (process_root.resolve(),) if process_root is not None else ()
    file_meta = meta if meta is not None else discover_input_file(source_path, roots=roots)
    if file_meta.source_type != "KIBOX":
        raise ValueError(f"KiBox reader expects an _i.csv runtime input, got source_type={file_meta.source_type} for {source_path.name}.")

    text = source_path.read_text(encoding="utf-8-sig", errors="ignore")
    lines = text.splitlines()
    sample = "\n".join(lines[:50])
    delimiter = _sniff_delimiter(sample)
    header_row = _find_header_row(lines, delimiter=delimiter, min_cols=6)

    table_lines = lines[header_row:]
    raw_rows = [line.split(delimiter) for line in table_lines if line.strip()]
    if not raw_rows:
        raise ValueError(f"KiBox file has no readable rows after header detection: {source_path.name}")

    header = _normalize_columns(raw_rows[0])
    body = raw_rows[1:]
    rows: List[Dict[str, object]] = []
    for index, raw_values in enumerate(body):
        row = {
            header[pos] if pos < len(header) else f"Col_{pos + 1}": (raw_values[pos] if pos < len(raw_values) else None)
            for pos in range(len(header))
        }
        row["BaseName"] = file_meta.basename
        row["Load_kW"] = file_meta.load_kw
        row["DIES_pct"] = file_meta.dies_pct
        row["BIOD_pct"] = file_meta.biod_pct
        row["EtOH_pct"] = file_meta.etoh_pct
        row["H2O_pct"] = file_meta.h2o_pct
        row["Sweep_Key"] = file_meta.sweep_key
        row["Sweep_Value"] = file_meta.sweep_value
        row["Sweep_Display_Label"] = file_meta.sweep_label or None
        row["Index"] = index
        rows.append(row)

    source_columns, cleaned_rows = _drop_unnamed_columns(header, rows)
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
    ]
    ordered_columns = leading_columns + [column for column in source_columns if column not in leading_columns]
    return KiboxReadResult(
        meta=file_meta,
        delimiter=delimiter,
        header_row=header_row,
        columns=ordered_columns,
        rows=cleaned_rows,
    )


def aggregate_kibox_mean(path: Path, *, process_root: Optional[Path] = None, meta: Optional[InputFileMeta] = None) -> KiboxAggregateResult:
    read_result = read_kibox_csv(path, process_root=process_root, meta=meta)
    numeric_columns = [column for column in read_result.columns if column not in {
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
    }]

    numeric_values: Dict[str, List[float]] = {column: [] for column in numeric_columns}
    for row in read_result.rows:
        for column in numeric_columns:
            parsed = _coerce_numeric_value(row.get(column))
            if parsed is not None:
                numeric_values[column].append(parsed)

    kept_columns = [column for column, values in numeric_values.items() if read_result.rows and (len(values) / len(read_result.rows)) >= 0.2]
    if not kept_columns:
        ranked = sorted(numeric_values.items(), key=lambda item: len(item[1]), reverse=True)
        kept_columns = [column for column, _values in ranked[:30]]

    aggregate_row: Dict[str, object] = {}
    for column in kept_columns:
        values = numeric_values[column]
        aggregate_row[f"KIBOX_{column}"] = (sum(values) / len(values)) if values else None

    aggregate_row.update(
        {
            "SourceFolder": _basename_source_folder_display(read_result.meta.basename),
            "Load_kW": read_result.meta.load_kw,
            "DIES_pct": read_result.meta.dies_pct,
            "BIOD_pct": read_result.meta.biod_pct,
            "EtOH_pct": read_result.meta.etoh_pct,
            "H2O_pct": read_result.meta.h2o_pct,
            "Sweep_Key": read_result.meta.sweep_key,
            "Sweep_Value": read_result.meta.sweep_value,
            "Sweep_Display_Label": read_result.meta.sweep_label or None,
            "KIBOX_N_files": 1,
        }
    )
    return KiboxAggregateResult(
        meta=read_result.meta,
        source_columns=read_result.columns,
        kept_columns=kept_columns,
        aggregate_row=aggregate_row,
    )


def summarize_kibox_read(result: KiboxReadResult) -> Dict[str, object]:
    return {
        "path": str(result.meta.path),
        "basename": result.meta.basename,
        "delimiter": result.delimiter,
        "header_row": result.header_row,
        "row_count": len(result.rows),
        "column_count": len(result.columns),
        "columns": result.columns,
        "source_type": result.meta.source_type,
        "load_kw": result.meta.load_kw,
        "sweep_key": result.meta.sweep_key,
        "sweep_value": result.meta.sweep_value,
    }


def summarize_kibox_aggregate(result: KiboxAggregateResult) -> Dict[str, object]:
    return {
        "path": str(result.meta.path),
        "basename": result.meta.basename,
        "source_type": result.meta.source_type,
        "load_kw": result.meta.load_kw,
        "kept_columns": result.kept_columns,
        "aggregate_row": result.aggregate_row,
    }
