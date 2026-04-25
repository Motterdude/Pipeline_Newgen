"""Stage: interactive sweep duplicate selector (fuel × sweep_value matrix)."""
from __future__ import annotations

from dataclasses import dataclass

from ..context import RuntimeContext


@dataclass(frozen=True)
class PromptSweepDuplicateSelectorStage:
    feature_key: str = "prompt_sweep_duplicate_selector"

    def run(self, ctx: RuntimeContext) -> None:
        if ctx.final_table is None:
            print("[INFO] prompt_sweep_duplicate_selector | final_table is None; skipping.")
            return
        if not ctx.sweep_active:
            return

        from ..sweep_axis import sweep_axis_label_for_col
        from ..sweep_duplicate_selector import (
            apply_sweep_duplicate_filter,
            prompt_sweep_duplicate_selector,
        )
        from ...ui.runtime_preflight.constants import SWEEP_BIN_VALUE_COL

        sel = ctx.normalized_state.selection if ctx.normalized_state else None
        if sel is None:
            return

        x_col = (
            SWEEP_BIN_VALUE_COL
            if SWEEP_BIN_VALUE_COL in ctx.final_table.columns
            else sel.sweep_x_col
        )
        axis_label = sweep_axis_label_for_col(
            x_col, sweep_x_col=sel.sweep_x_col, sweep_key=sel.sweep_key
        )

        selected = prompt_sweep_duplicate_selector(
            ctx.final_table,
            x_col=x_col,
            axis_label=axis_label,
            prompt_func=ctx.sweep_dup_prompt_func,
        )
        ctx.sweep_selected_basenames = selected

        if selected is not None:
            before = len(ctx.final_table)
            ctx.final_table = apply_sweep_duplicate_filter(ctx.final_table, selected)
            after = len(ctx.final_table)
            print(
                f"[OK] prompt_sweep_duplicate_selector | {after}/{before} rows kept"
            )
        else:
            print(
                "[OK] prompt_sweep_duplicate_selector | no duplicates found; all rows kept"
            )
