from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable, Dict, Tuple

from .constants import DEFAULT_SWEEP_KEY, RUNTIME_AGGREGATION_LOAD, SWEEP_VALUE_COL
from .models import OpenConversionStatus, RuntimePreflightSnapshot, RuntimeSelection
from .normalize import normalize_runtime_selection, normalize_sweep_key, normalize_sweep_x_col
from .prompt import PreflightPromptResult, prompt_runtime_preflight_via_cli, prompt_runtime_preflight_via_tk
from .scan import available_sweep_keys_from_paths, scan_open_conversion_status, scan_runtime_input_inventory


PromptFunc = Callable[[RuntimePreflightSnapshot, RuntimeSelection], PreflightPromptResult]
ConvertFunc = Callable[[OpenConversionStatus], None]


class PreflightCancelledError(RuntimeError):
    """Raised when the user cancels the runtime preflight."""


def _default_convert_missing_open_files(status: OpenConversionStatus) -> None:
    from ...adapters import export_open_paths, summarize_export_results

    if not status.missing_csv_opens:
        print("[INFO] Open converter | no missing .open files to convert.")
        return

    print(f"[INFO] Open converter | converting {len(status.missing_csv_opens)} missing .open file(s)...")
    results = export_open_paths(status.missing_csv_opens, name_mode="pipeline", export_type="res", separator="tab")
    summary = summarize_export_results(results)
    print(
        f"[INFO] Open converter | converted {summary['converted_files']} file(s) | "
        f"nonzero return codes: {summary['nonzero_returncodes']}"
    )


def build_runtime_preflight_snapshot(process_dir: Path) -> RuntimePreflightSnapshot:
    resolved_dir = Path(process_dir).expanduser().resolve()
    inventory = scan_runtime_input_inventory(resolved_dir)
    conversion_status = scan_open_conversion_status(resolved_dir)
    available_sweep_keys = available_sweep_keys_from_paths(inventory.candidate_paths)
    return RuntimePreflightSnapshot(
        process_dir=resolved_dir,
        inventory=inventory,
        conversion_status=conversion_status,
        available_sweep_keys=available_sweep_keys,
    )


def summarize_runtime_preflight_snapshot(snapshot: RuntimePreflightSnapshot) -> Dict[str, object]:
    return {
        "process_dir": str(snapshot.process_dir),
        "candidate_paths": len(snapshot.inventory.candidate_paths),
        "lv_count": snapshot.inventory.lv_count,
        "kibox_csv_count": snapshot.inventory.kibox_csv_count,
        "motec_csv_count": snapshot.inventory.motec_csv_count,
        "open_files": len(snapshot.conversion_status.open_files),
        "missing_csv_opens": len(snapshot.conversion_status.missing_csv_opens),
        "existing_csv_count": snapshot.conversion_status.existing_csv_count,
        "available_sweep_keys": list(snapshot.available_sweep_keys),
    }


def _default_initial_selection(snapshot: RuntimePreflightSnapshot) -> RuntimeSelection:
    sweep_key = snapshot.available_sweep_keys[0] if snapshot.available_sweep_keys else DEFAULT_SWEEP_KEY
    return RuntimeSelection(
        aggregation_mode=RUNTIME_AGGREGATION_LOAD,
        sweep_key=sweep_key,
        sweep_x_col=SWEEP_VALUE_COL,
    )


def _choose_prompt(snapshot: RuntimePreflightSnapshot, initial_selection: RuntimeSelection) -> PreflightPromptResult:
    try:
        return prompt_runtime_preflight_via_tk(snapshot, initial_selection)
    except Exception as exc:
        print(f"[WARN] Runtime preflight GUI failed: {exc}. Falling back to the terminal.")
        return prompt_runtime_preflight_via_cli(snapshot, initial_selection)


def choose_runtime_preflight(
    *,
    process_dir: Path,
    initial_selection: RuntimeSelection | None = None,
    prompt_func: PromptFunc | None = None,
    convert_func: ConvertFunc | None = None,
) -> RuntimeSelection:
    snapshot = build_runtime_preflight_snapshot(process_dir)
    current = normalize_runtime_selection(initial_selection or _default_initial_selection(snapshot))

    while True:
        snapshot = build_runtime_preflight_snapshot(process_dir)
        if current.sweep_key not in snapshot.available_sweep_keys:
            current = replace(current, sweep_key=normalize_sweep_key(snapshot.available_sweep_keys[0]))
        current = replace(current, sweep_x_col=normalize_sweep_x_col(current.sweep_x_col))

        action, selection = (prompt_func or _choose_prompt)(snapshot, current)
        current = normalize_runtime_selection(selection)

        if action == "cancel":
            raise PreflightCancelledError("Execution cancelled during runtime preflight.")
        if action == "convert":
            (convert_func or _default_convert_missing_open_files)(snapshot.conversion_status)
            continue
        if action == "continue":
            return current
        raise ValueError(f"Unsupported preflight action: {action!r}")
