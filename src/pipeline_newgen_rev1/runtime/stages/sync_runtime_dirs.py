"""Stage: resolve input/output directories and normalize runtime state.

Also materializes `ctx.feature_selection` / `ctx.enabled_features` once the
aggregation mode is known from the saved state.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...config import (
    RuntimeState,
    apply_runtime_path_overrides,
    default_runtime_state_path,
    load_runtime_state,
    save_runtime_state,
    sync_runtime_dirs_to_config_source,
)
from ...workflows.load_sweep.feature_flags import merge_feature_selection
from ..context import RuntimeContext
from ..runtime_dirs import choose_runtime_dirs


@dataclass(frozen=True)
class SyncRuntimeDirsStage:
    feature_key: str = "sync_runtime_dirs"

    def run(self, ctx: RuntimeContext) -> None:
        assert ctx.bundle is not None, "load_text_config must run before sync_runtime_dirs"

        resolved_state_path = (
            Path(ctx.state_path_override).expanduser().resolve()
            if ctx.state_path_override is not None
            else default_runtime_state_path()
        )
        state = load_runtime_state(resolved_state_path)
        _, input_dir, output_dir = apply_runtime_path_overrides(
            ctx.bundle.defaults,
            state,
            default_process_dir=ctx.project_root / "raw",
            default_out_dir=ctx.project_root / "out",
        )
        input_dir, output_dir = choose_runtime_dirs(
            initial_input_dir=input_dir,
            initial_out_dir=output_dir,
            runtime_state=state,
            prompt_func=ctx.runtime_dirs_prompt_func,
            force_prompt=ctx.prompt_runtime_dirs,
        )
        if ctx.process_dir_override is not None:
            input_dir = Path(ctx.process_dir_override).expanduser().resolve()
        if ctx.out_dir_override is not None:
            output_dir = Path(ctx.out_dir_override).expanduser().resolve()

        ctx.resolved_state_path = resolved_state_path
        ctx.state = state
        ctx.input_dir = input_dir
        ctx.output_dir = output_dir
        ctx.selection = state.selection

        # Now that we know the aggregation mode, materialize the feature plan.
        ctx.feature_selection = merge_feature_selection(state.selection.aggregation_mode, overrides=None)
        ctx.enabled_features = {key for key, value in ctx.feature_selection.items() if value}
