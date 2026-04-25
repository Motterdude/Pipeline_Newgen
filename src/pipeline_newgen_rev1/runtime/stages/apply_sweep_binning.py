"""Stage: cluster sweep values into stable bins."""
from __future__ import annotations

from dataclasses import dataclass

from ..context import RuntimeContext


@dataclass(frozen=True)
class ApplySweepBinningStage:
    feature_key: str = "apply_sweep_binning"

    def run(self, ctx: RuntimeContext) -> None:
        if ctx.final_table is None:
            print("[INFO] apply_sweep_binning | final_table is None; skipping.")
            return
        sel = ctx.normalized_state.selection if ctx.normalized_state else None
        if sel is None:
            return

        from ..sweep_binning import apply_sweep_binning

        ctx.final_table = apply_sweep_binning(
            ctx.final_table,
            x_col=sel.sweep_x_col,
            tol=sel.sweep_bin_tol,
            sweep_active=ctx.sweep_active,
        )
