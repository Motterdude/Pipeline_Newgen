"""Stage: set sweep axis context fields for downstream plot stages."""
from __future__ import annotations

from dataclasses import dataclass

from ..context import RuntimeContext


@dataclass(frozen=True)
class RewritePlotAxisToSweepStage:
    feature_key: str = "rewrite_plot_axis_to_sweep"

    def run(self, ctx: RuntimeContext) -> None:
        if not ctx.sweep_active:
            print("[INFO] rewrite_plot_axis_to_sweep | sweep not active; skipping.")
            return

        from ..sweep_axis import sweep_axis_label_for_col, sweep_axis_token_for_col
        from ...ui.runtime_preflight.constants import SWEEP_BIN_VALUE_COL

        sel = ctx.normalized_state.selection if ctx.normalized_state else None
        if sel is None:
            return

        ctx.sweep_effective_x_col = SWEEP_BIN_VALUE_COL
        ctx.sweep_axis_label = sweep_axis_label_for_col(
            sel.sweep_x_col,
            sweep_x_col=sel.sweep_x_col,
            sweep_key=sel.sweep_key,
        )
        ctx.sweep_axis_token = sweep_axis_token_for_col(
            sel.sweep_x_col,
            sweep_x_col=sel.sweep_x_col,
            sweep_key=sel.sweep_key,
        )

        print(
            f"[OK] rewrite_plot_axis_to_sweep | effective_x={ctx.sweep_effective_x_col}, "
            f"label={ctx.sweep_axis_label}, token={ctx.sweep_axis_token}"
        )
