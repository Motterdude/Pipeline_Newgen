"""Stage: run_compare_plots — subida x descida comparison within a campaign."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..context import RuntimeContext


@dataclass(frozen=True)
class RunComparePlotsStage:
    feature_key: str = "run_compare_plots"

    def run(self, ctx: RuntimeContext) -> None:
        if ctx.final_table is None:
            print("[INFO] run_compare_plots | final_table is None; skipping.")
            return
        if ctx.output_dir is None:
            raise RuntimeError("run_compare_plots requires ctx.output_dir to be set.")

        from ..compare_plots import iter_compare_plot_groups
        from ..unitary_plots import make_plots_from_config_with_summary

        plots_list = ctx.bundle.plots if ctx.bundle else []
        plots_df = pd.DataFrame(plots_list) if plots_list else pd.DataFrame()
        mappings = ctx.bundle.mappings if ctx.bundle else {}

        if plots_df.empty:
            print("[INFO] run_compare_plots | no plot config; skipping.")
            return

        groups = iter_compare_plot_groups(ctx.final_table, root=ctx.output_dir / "plots")
        if not groups:
            print("[INFO] run_compare_plots | no subida/descida pairs found; skipping.")
            return

        sel = ctx.normalized_state.selection if ctx.normalized_state else None
        total_pngs = 0
        for group_key, plot_dir, group_df in groups:
            plot_dir.mkdir(parents=True, exist_ok=True)
            summary = make_plots_from_config_with_summary(
                group_df,
                plots_df,
                mappings=mappings,
                plot_dir=plot_dir,
                series_col="_COMPARE_SERIES",
                sweep_active=ctx.sweep_active,
                sweep_x_col=sel.sweep_x_col if sel else "",
                sweep_effective_x_col=ctx.sweep_effective_x_col,
                sweep_axis_label=ctx.sweep_axis_label,
                sweep_axis_token=ctx.sweep_axis_token,
            )
            n = summary.get("plots_saved", 0) if isinstance(summary, dict) else 0
            total_pngs += n

        print(f"[OK] run_compare_plots | {len(groups)} groups, {total_pngs} PNGs generated.")
