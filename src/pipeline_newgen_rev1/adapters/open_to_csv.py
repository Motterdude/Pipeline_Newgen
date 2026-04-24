from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence


DEFAULT_OPENTOCSV_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Kistler\CSVExportSeriell\OpenToCSV.exe"),
    Path(r"C:\Program Files\Kistler\CSVExportSeriell\OpenToCSV.exe"),
]
OPEN_TO_CSV_ENV_KEYS = (
    "PIPELINE_NEWGEN_OPENTOCSV_PATH",
    "PIPELINE30_OPENTOCSV_PATH",
    "OPENTOCSV_PATH",
)
SUPPORTED_EXPORT_TYPES = {"res", "sig", "tim"}
SUPPORTED_NAME_MODES = {"source", "pipeline", "tool"}
PIPELINE_RESULT_SUFFIX = "_i.csv"
OPEN_TO_CSV_SETTINGS_FILENAME = "open_to_csv_settings.json"

LogCallback = Callable[[str, bool], None]


@dataclass(frozen=True)
class ExportRequest:
    source_open: Path
    destination_dir: Path
    export_type: str = "res"
    separator: str = "tab"
    include_cycle_number: bool = True
    cycles: Optional[str] = None
    name_mode: str = "pipeline"
    output_name: Optional[str] = None


@dataclass(frozen=True)
class ExportResult:
    source_open: Path
    exported_csv: Path
    tool_generated_csv: Path
    returncode: int
    stdout: str
    stderr: str


def default_open_to_csv_settings_path() -> Path:
    from ..config import default_app_state_dir

    return default_app_state_dir() / OPEN_TO_CSV_SETTINGS_FILENAME


def load_open_to_csv_settings(path: Optional[Path] = None) -> dict:
    target = default_open_to_csv_settings_path() if path is None else Path(path).expanduser().resolve()
    try:
        if not target.exists():
            return {}
        return json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_open_to_csv_settings(settings: dict, path: Optional[Path] = None) -> None:
    target = default_open_to_csv_settings_path() if path is None else Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(settings, indent=2, ensure_ascii=True), encoding="utf-8")


def remember_open_to_csv_path(path: Path, settings_path: Optional[Path] = None) -> None:
    settings = load_open_to_csv_settings(settings_path)
    settings["open_to_csv_path"] = str(Path(path).expanduser().resolve())
    save_open_to_csv_settings(settings, settings_path)


def _saved_open_to_csv_path(settings_path: Optional[Path] = None) -> Optional[Path]:
    settings = load_open_to_csv_settings(settings_path)
    raw = str(settings.get("open_to_csv_path", "")).strip()
    if not raw:
        return None
    try:
        return Path(raw).expanduser().resolve()
    except Exception:
        return None


def find_open_to_csv_path(explicit_path: Optional[Path] = None, *, settings_path: Optional[Path] = None) -> Path:
    if explicit_path is not None:
        candidate = Path(explicit_path).expanduser().resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"OpenToCSV nao encontrado em: {candidate}")
        remember_open_to_csv_path(candidate, settings_path)
        return candidate

    candidates: list[Path] = []
    for env_key in OPEN_TO_CSV_ENV_KEYS:
        raw = str(os.environ.get(env_key, "")).strip()
        if not raw:
            continue
        try:
            candidates.append(Path(raw).expanduser().resolve())
        except Exception:
            continue

    saved_candidate = _saved_open_to_csv_path(settings_path)
    if saved_candidate is not None:
        candidates.append(saved_candidate)

    for default_candidate in DEFAULT_OPENTOCSV_CANDIDATES:
        candidates.append(default_candidate)

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)

    for candidate in deduped:
        if candidate.exists():
            remember_open_to_csv_path(candidate, settings_path)
            return candidate

    raise FileNotFoundError(
        "Nao encontrei o OpenToCSV. Configure um caminho explicito ou defina "
        + ", ".join(OPEN_TO_CSV_ENV_KEYS)
        + "."
    )


def build_open_to_csv_command(converter_path: Path) -> list[str]:
    resolved = Path(converter_path).expanduser().resolve()
    suffix = resolved.suffix.lower()
    if suffix == ".py":
        return [sys.executable, str(resolved)]
    if suffix in {".cmd", ".bat"}:
        return ["cmd.exe", "/c", str(resolved)]
    if suffix == ".ps1":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(resolved)]
    return [str(resolved)]


def _normalize_export_type(export_type: str) -> str:
    value = str(export_type).strip().lower()
    if value not in SUPPORTED_EXPORT_TYPES:
        raise ValueError(f"export_type invalido: {export_type}. Use um de {sorted(SUPPORTED_EXPORT_TYPES)}.")
    return value


def _normalize_separator(separator: str) -> str:
    value = str(separator).strip().lower()
    if value in {"tab", "\\t", "t"}:
        return "tab"
    if value in {",", "comma"}:
        return ","
    if value in {";", "semicolon"}:
        return ";"
    raise ValueError("separator invalido. Use 'tab', ',' ou ';'.")


def _normalize_name_mode(name_mode: str) -> str:
    value = str(name_mode).strip().lower()
    if value not in SUPPORTED_NAME_MODES:
        raise ValueError(f"name_mode invalido: {name_mode}. Use um de {sorted(SUPPORTED_NAME_MODES)}.")
    return value


def _normalize_output_name(output_name: Optional[str]) -> Optional[str]:
    if output_name is None:
        return None
    value = str(output_name).strip()
    if not value:
        return None
    if not value.lower().endswith(".csv"):
        value += ".csv"
    return Path(value).name


def _build_converter_args(
    source_dir: Path,
    *,
    export_type: str,
    separator: str,
    include_cycle_number: bool,
    cycles: Optional[str],
) -> list[str]:
    args = [f"sourcepath={source_dir}", f"type={export_type}"]
    if separator == "tab":
        args.append("sep=tab")
    elif separator == ",":
        args.append("sep=,")
    elif separator != ";":
        raise ValueError(f"Separador nao suportado: {separator}")
    if include_cycle_number:
        args.append("cno")
    if cycles:
        args.append(f"cycles={cycles}")
    return args


def _default_output_name(source_open: Path, *, name_mode: str, export_type: str) -> str:
    if name_mode == "tool":
        return f"{source_open.stem}_{export_type}.csv"
    if name_mode == "pipeline":
        if export_type != "res":
            raise ValueError("name_mode='pipeline' exige export_type='res'.")
        return f"{source_open.stem}{PIPELINE_RESULT_SUFFIX}"
    return f"{source_open.stem}.csv"


def build_output_name(
    source_open: Path,
    *,
    name_mode: str,
    export_type: str,
    output_name: Optional[str] = None,
) -> str:
    normalized_output_name = _normalize_output_name(output_name)
    if normalized_output_name is not None:
        return normalized_output_name
    return _default_output_name(
        Path(source_open),
        name_mode=_normalize_name_mode(name_mode),
        export_type=_normalize_export_type(export_type),
    )


def planned_pipeline_csv_name(source_open: Path) -> str:
    return build_output_name(Path(source_open), name_mode="pipeline", export_type="res")


def planned_pipeline_csv_path(source_open: Path) -> Path:
    source = Path(source_open)
    return source.with_name(planned_pipeline_csv_name(source))


def _find_tool_output(export_dir: Path, *, source_stem: str, export_type: str) -> Path:
    expected = export_dir / f"{source_stem}_{export_type}.csv"
    if expected.exists():
        return expected
    csvs = sorted(export_dir.glob("*.csv"))
    if len(csvs) == 1:
        return csvs[0]
    matches = [path for path in csvs if path.stem.lower().startswith(source_stem.lower())]
    if len(matches) == 1:
        return matches[0]
    raise FileNotFoundError(
        f"Nao encontrei o CSV exportado em {export_dir}. Esperava '{expected.name}' e achei {[path.name for path in csvs]}."
    )


def _run_converter(cmd: Sequence[str], *, cwd: Path, log_callback: Optional[LogCallback]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(cmd),
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if log_callback is not None and completed.stdout:
        log_callback(completed.stdout, False)
    if log_callback is not None and completed.stderr:
        log_callback(completed.stderr, True)
    return completed


def export_open_file(
    request: ExportRequest,
    *,
    converter_path: Optional[Path] = None,
    settings_path: Optional[Path] = None,
    log_callback: Optional[LogCallback] = None,
) -> ExportResult:
    source_open = Path(request.source_open).expanduser().resolve()
    if not source_open.exists():
        raise FileNotFoundError(f"Arquivo .open nao encontrado: {source_open}")
    if source_open.suffix.lower() != ".open":
        raise ValueError(f"Arquivo de entrada nao e .open: {source_open}")

    export_type = _normalize_export_type(request.export_type)
    separator = _normalize_separator(request.separator)
    name_mode = _normalize_name_mode(request.name_mode)
    output_name = _normalize_output_name(request.output_name)
    destination_dir = Path(request.destination_dir).expanduser().resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)

    resolved_converter = find_open_to_csv_path(converter_path, settings_path=settings_path)
    converter_cmd = build_open_to_csv_command(resolved_converter)

    with tempfile.TemporaryDirectory(prefix="pipeline_newgen_open_to_csv_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        source_dir = temp_dir / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        temp_open = source_dir / source_open.name
        shutil.copy2(source_open, temp_open)

        cmd = [
            *converter_cmd,
            *_build_converter_args(
                source_dir,
                export_type=export_type,
                separator=separator,
                include_cycle_number=request.include_cycle_number,
                cycles=request.cycles,
            ),
        ]
        completed = _run_converter(cmd, cwd=resolved_converter.parent, log_callback=log_callback)
        export_dir = source_dir / "CSVExport"
        try:
            tool_generated_csv = _find_tool_output(export_dir, source_stem=source_open.stem, export_type=export_type)
        except FileNotFoundError as exc:
            if completed.returncode != 0:
                raise RuntimeError(
                    f"OpenToCSV falhou para {source_open.name} com codigo {completed.returncode}. "
                    f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
                ) from exc
            raise

        final_name = build_output_name(
            source_open,
            name_mode=name_mode,
            export_type=export_type,
            output_name=output_name,
        )
        final_path = destination_dir / final_name
        shutil.copy2(tool_generated_csv, final_path)
        return ExportResult(
            source_open=source_open,
            exported_csv=final_path,
            tool_generated_csv=tool_generated_csv,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def _iter_open_files(input_path: Path) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
        return
    for path in sorted(input_path.rglob("*.open")):
        if path.is_file():
            yield path


def _destination_dir_for(source_open: Path, *, input_root: Path, output_root: Optional[Path]) -> Path:
    if output_root is None:
        return source_open.parent
    if input_root.is_file():
        return output_root
    rel_parent = source_open.parent.relative_to(input_root)
    return output_root / rel_parent


def export_open_inputs(
    input_path: Path,
    *,
    output_root: Optional[Path] = None,
    converter_path: Optional[Path] = None,
    settings_path: Optional[Path] = None,
    export_type: str = "res",
    separator: str = "tab",
    include_cycle_number: bool = True,
    cycles: Optional[str] = None,
    name_mode: str = "pipeline",
    output_name: Optional[str] = None,
    log_callback: Optional[LogCallback] = None,
) -> list[ExportResult]:
    input_path = Path(input_path).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Entrada nao encontrada: {input_path}")
    if input_path.is_file() and input_path.suffix.lower() != ".open":
        raise ValueError(f"Entrada de arquivo precisa ser .open: {input_path}")
    if input_path.is_dir() and output_name:
        raise ValueError("output_name so pode ser usado quando a entrada for um unico arquivo .open.")

    files = list(_iter_open_files(input_path))
    if not files:
        raise FileNotFoundError(f"Nao encontrei arquivos .open em: {input_path}")

    resolved_output_root = None if output_root is None else Path(output_root).expanduser().resolve()
    results: list[ExportResult] = []
    for source_open in files:
        destination_dir = _destination_dir_for(source_open, input_root=input_path, output_root=resolved_output_root)
        result = export_open_file(
            ExportRequest(
                source_open=source_open,
                destination_dir=destination_dir,
                export_type=export_type,
                separator=separator,
                include_cycle_number=include_cycle_number,
                cycles=cycles,
                name_mode=name_mode,
                output_name=output_name,
            ),
            converter_path=converter_path,
            settings_path=settings_path,
            log_callback=log_callback,
        )
        results.append(result)
    return results


def export_open_paths(
    source_opens: Sequence[Path],
    *,
    converter_path: Optional[Path] = None,
    settings_path: Optional[Path] = None,
    export_type: str = "res",
    separator: str = "tab",
    include_cycle_number: bool = True,
    cycles: Optional[str] = None,
    name_mode: str = "pipeline",
    log_callback: Optional[LogCallback] = None,
) -> list[ExportResult]:
    results: list[ExportResult] = []
    for source_open in source_opens:
        path = Path(source_open).expanduser().resolve()
        result = export_open_file(
            ExportRequest(
                source_open=path,
                destination_dir=path.parent,
                export_type=export_type,
                separator=separator,
                include_cycle_number=include_cycle_number,
                cycles=cycles,
                name_mode=name_mode,
            ),
            converter_path=converter_path,
            settings_path=settings_path,
            log_callback=log_callback,
        )
        results.append(result)
    return results


def summarize_export_results(results: Sequence[ExportResult]) -> dict:
    return {
        "converted_files": len(results),
        "nonzero_returncodes": sum(1 for result in results if result.returncode != 0),
        "outputs": [str(result.exported_csv) for result in results],
    }
