from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from ..adapters import (
    InputFileMeta,
    aggregate_kibox_mean,
    discover_runtime_inputs,
    read_labview_xlsx,
    read_kibox_csv,
    read_motec_csv,
    summarize_discovered_inputs,
    summarize_kibox_aggregate,
    summarize_kibox_read,
    summarize_labview_read,
    summarize_motec_read,
)
from ..config import (
    RuntimeState,
    save_runtime_state,
    sync_runtime_dirs_to_config_source,
)
from .context import RuntimeContext
from .plot_point_filter import (
    apply_plot_point_filter,
    prompt_plot_point_filter,
    prompt_plot_point_filter_from_metas,
)
from .runtime_dirs import PromptRuntimeDirsFunc
from .stages import STAGE_PIPELINE_ORDER, STAGE_REGISTRY


RUNTIME_OUTPUT_DIRNAME = "pipeline_newgen_runtime"
SUMMARY_JSON_NAME = "newgen_runtime_summary.json"
SUMMARY_XLSX_NAME = "newgen_runtime_summary.xlsx"


@dataclass(frozen=True)
class RuntimeExecutionResult:
    summary: Dict[str, Any]
    summary_json_path: Path
    summary_xlsx_path: Path


def _records_frame(records: List[Dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def _write_summary_workbook(
    path: Path,
    *,
    discovery_summary: Dict[str, Any],
    labview_rows: List[Dict[str, Any]],
    labview_plot_rows: List[Dict[str, Any]],
    motec_rows: List[Dict[str, Any]],
    kibox_rows: List[Dict[str, Any]],
    kibox_aggregate_rows: List[Dict[str, Any]],
    plot_filter_rows: List[Dict[str, Any]],
    top_summary: Dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        _records_frame([top_summary]).to_excel(writer, sheet_name="summary", index=False)
        _records_frame(discovery_summary.get("files", [])).to_excel(writer, sheet_name="inputs", index=False)
        _records_frame(labview_rows).to_excel(writer, sheet_name="labview", index=False)
        _records_frame(labview_plot_rows).to_excel(writer, sheet_name="labview_plot_filter", index=False)
        _records_frame(motec_rows).to_excel(writer, sheet_name="motec", index=False)
        _records_frame(kibox_rows).to_excel(writer, sheet_name="kibox_raw", index=False)
        _records_frame(kibox_aggregate_rows).to_excel(writer, sheet_name="kibox_aggregate", index=False)
        _records_frame(plot_filter_rows).to_excel(writer, sheet_name="plot_filter", index=False)


def _plot_points_as_rows(selected_points: Sequence[tuple[str, float]]) -> List[Dict[str, Any]]:
    return [
        {"fuel_label": fuel_label, "load_kw": load_kw}
        for fuel_label, load_kw in selected_points
    ]


def _finalize_runtime_state(ctx: RuntimeContext) -> None:
    """Persist the runtime state after preflight may have updated selection,
    then sync the bundle's config source to the resolved directories."""
    assert ctx.resolved_state_path is not None
    assert ctx.state is not None
    assert ctx.bundle is not None
    assert ctx.input_dir is not None and ctx.output_dir is not None
    assert ctx.selection is not None

    ctx.normalized_state = save_runtime_state(
        ctx.resolved_state_path,
        RuntimeState(
            raw_input_dir=ctx.input_dir,
            out_dir=ctx.output_dir,
            selection=ctx.selection,
            helper_configured=True,
            dirs_configured_in_gui=True,
            config_dir=(
                ctx.text_config_dir
                or ctx.bundle.text_dir
                or (ctx.project_root / "config" / "pipeline29_text")
            ),
            extra=dict(ctx.state.extra),
        ),
    )
    sync_runtime_dirs_to_config_source(ctx.bundle, ctx.input_dir, ctx.output_dir)


def _discover_and_read_inputs(ctx: RuntimeContext) -> None:
    """Core scaffolding (not yet feature-gated): discovery + optional plot-point
    prompt (load mode only) + LV/MoTeC/KiBox reading loop."""
    assert ctx.input_dir is not None
    assert ctx.normalized_state is not None

    ctx.discovery = discover_runtime_inputs(ctx.input_dir)
    ctx.discovery_summary = summarize_discovered_inputs(ctx.discovery)

    if ctx.prompt_plot_filter and ctx.normalized_state.selection.aggregation_mode == "load":
        lv_files: List[InputFileMeta] = [
            file_meta
            for file_meta in ctx.discovery.files
            if file_meta.source_type == "LABVIEW" and file_meta.path.suffix.lower() == ".xlsx"
        ]
        print("[INFO] Abrindo filtro de pontos para os plots finais...")
        ctx.selected_plot_points = prompt_plot_point_filter_from_metas(
            lv_files,
            prompt_func=ctx.plot_filter_prompt_func,
        )
    elif ctx.normalized_state.selection.aggregation_mode == "sweep":
        print("[INFO] Modo sweep ativo: pulando o filtro de pontos Fuel x Load do fluxo convencional.")

    for file_meta in ctx.discovery.files:
        try:
            if file_meta.source_type == "LABVIEW" and file_meta.path.suffix.lower() == ".xlsx":
                labview_read = read_labview_xlsx(file_meta.path, process_root=ctx.input_dir, meta=file_meta)
                ctx.labview_rows.append(summarize_labview_read(labview_read))
                ctx.labview_frames.append(pd.DataFrame(labview_read.rows))
            elif file_meta.source_type == "MOTEC" and file_meta.path.suffix.lower() == ".csv":
                ctx.motec_rows.append(
                    summarize_motec_read(read_motec_csv(file_meta.path, process_root=ctx.input_dir, meta=file_meta))
                )
            elif file_meta.source_type == "KIBOX" and file_meta.path.suffix.lower() == ".csv":
                kibox_read = read_kibox_csv(file_meta.path, process_root=ctx.input_dir, meta=file_meta)
                ctx.kibox_rows.append(summarize_kibox_read(kibox_read))
                ctx.kibox_aggregate_rows.append(
                    summarize_kibox_aggregate(
                        aggregate_kibox_mean(file_meta.path, process_root=ctx.input_dir, meta=file_meta)
                    )
                )
        except Exception as exc:
            ctx.errors.append(f"{file_meta.path.name}: {exc}")


def _apply_plot_filter(ctx: RuntimeContext) -> None:
    """Core scaffolding: apply the selected plot-point filter to the combined
    LabVIEW frame and materialize the plot-filter rows used by the summary."""
    assert ctx.normalized_state is not None

    labview_plot_frame = pd.DataFrame()
    if ctx.labview_frames:
        combined_labview = pd.concat(ctx.labview_frames, ignore_index=True)
        if (
            ctx.prompt_plot_filter
            and ctx.normalized_state.selection.aggregation_mode == "load"
            and ctx.selected_plot_points is None
        ):
            ctx.selected_plot_points = prompt_plot_point_filter(
                combined_labview,
                prompt_func=ctx.plot_filter_prompt_func,
            )
        labview_plot_frame = apply_plot_point_filter(combined_labview, ctx.selected_plot_points)
        if not labview_plot_frame.empty:
            keep_columns = [
                column
                for column in [
                    "BaseName",
                    "Fuel_Label",
                    "Load_kW",
                    "DIES_pct",
                    "BIOD_pct",
                    "EtOH_pct",
                    "H2O_pct",
                    "Sweep_Key",
                    "Sweep_Value",
                ]
                if column in labview_plot_frame.columns
            ]
            if keep_columns:
                ctx.labview_plot_rows = labview_plot_frame[keep_columns].to_dict(orient="records")
            else:
                ctx.labview_plot_rows = labview_plot_frame.head(200).to_dict(orient="records")


def _write_summary_artifacts(ctx: RuntimeContext) -> None:
    """Core scaffolding: build the summary dict and write the JSON + XLSX
    artifacts into `<out_dir>/pipeline_newgen_runtime/`."""
    assert ctx.output_dir is not None
    assert ctx.normalized_state is not None
    assert ctx.bundle is not None

    ctx.artifacts_dir = ctx.output_dir / RUNTIME_OUTPUT_DIRNAME
    ctx.artifacts_dir.mkdir(parents=True, exist_ok=True)
    ctx.summary_json_path = ctx.artifacts_dir / SUMMARY_JSON_NAME
    ctx.summary_xlsx_path = ctx.artifacts_dir / SUMMARY_XLSX_NAME

    plot_filter_rows = _plot_points_as_rows(
        sorted(ctx.selected_plot_points or [], key=lambda item: (item[0], item[1]))
    )

    ctx.summary = {
        "project_root": str(ctx.project_root),
        "config_source": ctx.bundle.source_kind,
        "config_dir": str(ctx.text_config_dir or ctx.bundle.text_dir or ""),
        "process_dir": str(ctx.input_dir),
        "out_dir": str(ctx.output_dir),
        "aggregation_mode": ctx.normalized_state.selection.aggregation_mode,
        "sweep_key": ctx.normalized_state.selection.sweep_key,
        "sweep_x_col": ctx.normalized_state.selection.sweep_x_col,
        "sweep_bin_tol": ctx.normalized_state.selection.sweep_bin_tol,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_inputs": ctx.discovery_summary["total_files"],
        "labview_files": len(ctx.labview_rows),
        "labview_plot_rows": len(ctx.labview_plot_rows),
        "motec_files": len(ctx.motec_rows),
        "kibox_files": len(ctx.kibox_rows),
        "kibox_aggregate_rows": len(ctx.kibox_aggregate_rows),
        "selected_plot_points_count": len(plot_filter_rows),
        "selected_plot_points": plot_filter_rows,
        "errors": ctx.errors,
        "summary_json_path": str(ctx.summary_json_path),
        "summary_xlsx_path": str(ctx.summary_xlsx_path),
    }

    ctx.summary_json_path.write_text(
        json.dumps(ctx.summary, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    _write_summary_workbook(
        ctx.summary_xlsx_path,
        discovery_summary=ctx.discovery_summary,
        labview_rows=ctx.labview_rows,
        labview_plot_rows=ctx.labview_plot_rows,
        motec_rows=ctx.motec_rows,
        kibox_rows=ctx.kibox_rows,
        kibox_aggregate_rows=ctx.kibox_aggregate_rows,
        plot_filter_rows=plot_filter_rows,
        top_summary=ctx.summary,
    )


def run_load_sweep(
    *,
    project_root: Path,
    config_source: str = "auto",
    text_config_dir: Optional[Path] = None,
    excel_path: Optional[Path] = None,
    state_path: Optional[Path] = None,
    process_dir: Optional[Path] = None,
    out_dir: Optional[Path] = None,
    use_preflight: bool = False,
    prompt_runtime_dirs: bool = False,
    prompt_plot_filter: bool = False,
    _runtime_dirs_prompt_func: Optional[PromptRuntimeDirsFunc] = None,
    _plot_filter_prompt_func: Optional[Any] = None,
) -> RuntimeExecutionResult:
    ctx = RuntimeContext.from_kwargs(
        project_root=project_root,
        config_source=config_source,
        text_config_dir=text_config_dir,
        excel_path=excel_path,
        state_path=state_path,
        process_dir=process_dir,
        out_dir=out_dir,
        use_preflight=use_preflight,
        prompt_runtime_dirs=prompt_runtime_dirs,
        prompt_plot_filter=prompt_plot_filter,
        runtime_dirs_prompt_func=_runtime_dirs_prompt_func,
        plot_filter_prompt_func=_plot_filter_prompt_func,
    )

    for feature_key in STAGE_PIPELINE_ORDER:
        stage = STAGE_REGISTRY.get(feature_key)
        if stage is None:
            continue
        stage.run(ctx)

    _finalize_runtime_state(ctx)
    _discover_and_read_inputs(ctx)
    _apply_plot_filter(ctx)
    _write_summary_artifacts(ctx)

    assert ctx.summary_json_path is not None and ctx.summary_xlsx_path is not None
    return RuntimeExecutionResult(
        summary=ctx.summary,
        summary_json_path=ctx.summary_json_path,
        summary_xlsx_path=ctx.summary_xlsx_path,
    )
