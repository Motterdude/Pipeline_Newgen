"""Native stage: generate unitary plots from ctx.final_table + plots config."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..context import RuntimeContext
from ..unitary_plots import make_plots_from_config_with_summary


@dataclass(frozen=True)
class RunUnitaryPlotsStage:
    feature_key: str = "run_unitary_plots"

    def run(self, ctx: RuntimeContext) -> None:
        if ctx.final_table is None:
            print("[INFO] run_unitary_plots | nothing to plot (final_table is None)")
            return
        if ctx.output_dir is None:
            raise RuntimeError(
                "run_unitary_plots requires ctx.output_dir to be resolved first"
            )

        plot_dir = Path(ctx.output_dir) / "plots"
        plot_dir.mkdir(parents=True, exist_ok=True)

        plots_list = ctx.bundle.plots if ctx.bundle is not None else []
        plots_df = pd.DataFrame(plots_list) if plots_list else pd.DataFrame()
        mappings = ctx.bundle.mappings if ctx.bundle is not None else {}

        sel = ctx.normalized_state.selection if ctx.normalized_state else None
        ctx.unitary_plot_summary = make_plots_from_config_with_summary(
            ctx.final_table,
            plots_df,
            mappings,
            plot_dir=plot_dir,
            sweep_active=ctx.sweep_active,
            sweep_x_col=sel.sweep_x_col if sel else "",
            sweep_effective_x_col=ctx.sweep_effective_x_col,
            sweep_axis_label=ctx.sweep_axis_label,
            sweep_axis_token=ctx.sweep_axis_token,
        )
        summary = ctx.unitary_plot_summary or {}
        generated = summary.get("generated", 0)
        skipped = summary.get("skipped", 0)
        disabled = summary.get("disabled", 0)
        print(
            f"[OK] run_unitary_plots | generated={generated} "
            f"skipped={skipped} disabled={disabled} dir={plot_dir}"
        )
