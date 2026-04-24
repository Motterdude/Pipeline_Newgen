"""RuntimeContext: the assembly line conveyor of the new factory.

Each stage registered in `runtime/stages/` mutates this context in place.
The runner wires the kwargs in, loops over the stages, then reads the
final artifacts and summary out.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set

import pandas as pd

from ..config import ConfigBundle, RuntimeState
from ..ui.runtime_preflight.models import RuntimeSelection
from .runtime_dirs import PromptRuntimeDirsFunc


@dataclass
class RuntimeContext:
    # --- Invariant inputs (set by RuntimeContext.from_kwargs) ---
    project_root: Path
    config_source: str = "auto"
    text_config_dir: Optional[Path] = None
    excel_path: Optional[Path] = None
    state_path_override: Optional[Path] = None
    process_dir_override: Optional[Path] = None
    out_dir_override: Optional[Path] = None
    use_preflight: bool = False
    prompt_runtime_dirs: bool = False
    prompt_plot_filter: bool = False
    runtime_dirs_prompt_func: Optional[PromptRuntimeDirsFunc] = None
    plot_filter_prompt_func: Optional[Callable[..., Any]] = None

    # --- Populated by stages ---
    bundle: Optional[ConfigBundle] = None
    resolved_state_path: Optional[Path] = None
    state: Optional[RuntimeState] = None
    input_dir: Optional[Path] = None
    output_dir: Optional[Path] = None
    selection: Optional[RuntimeSelection] = None
    normalized_state: Optional[RuntimeState] = None
    feature_selection: Dict[str, bool] = field(default_factory=dict)
    enabled_features: Set[str] = field(default_factory=set)

    # --- Populated by core (non-feature-gated) helpers in runner.py ---
    discovery: Any = None
    discovery_summary: Dict[str, Any] = field(default_factory=dict)
    labview_rows: List[Dict[str, Any]] = field(default_factory=list)
    labview_plot_rows: List[Dict[str, Any]] = field(default_factory=list)
    motec_rows: List[Dict[str, Any]] = field(default_factory=list)
    kibox_rows: List[Dict[str, Any]] = field(default_factory=list)
    kibox_aggregate_rows: List[Dict[str, Any]] = field(default_factory=list)
    labview_frames: List[pd.DataFrame] = field(default_factory=list)
    selected_plot_points: Optional[Set[tuple[str, float]]] = None
    errors: List[str] = field(default_factory=list)
    artifacts_dir: Optional[Path] = None
    summary_json_path: Optional[Path] = None
    summary_xlsx_path: Optional[Path] = None
    summary: Dict[str, Any] = field(default_factory=dict)

    # --- Populated by bridge stages that produce legacy-equivalent artifacts ---
    ponto: Optional[pd.DataFrame] = None
    fuel_properties: Optional[pd.DataFrame] = None
    kibox_agg: Optional[pd.DataFrame] = None
    motec_ponto: Optional[pd.DataFrame] = None
    final_table: Optional[pd.DataFrame] = None
    lv_kpis_path: Optional[Path] = None
    legacy_bundle: Any = None  # Pipeline29ConfigBundle from the frozen legacy module; cached across bridge stages
    unitary_plot_summary: Optional[Dict[str, Any]] = None

    @classmethod
    def from_kwargs(
        cls,
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
        runtime_dirs_prompt_func: Optional[PromptRuntimeDirsFunc] = None,
        plot_filter_prompt_func: Optional[Callable[..., Any]] = None,
    ) -> "RuntimeContext":
        return cls(
            project_root=Path(project_root).expanduser().resolve(),
            config_source=config_source,
            text_config_dir=text_config_dir,
            excel_path=excel_path,
            state_path_override=state_path,
            process_dir_override=process_dir,
            out_dir_override=out_dir,
            use_preflight=use_preflight,
            prompt_runtime_dirs=prompt_runtime_dirs,
            prompt_plot_filter=prompt_plot_filter,
            runtime_dirs_prompt_func=runtime_dirs_prompt_func,
            plot_filter_prompt_func=plot_filter_prompt_func,
        )
