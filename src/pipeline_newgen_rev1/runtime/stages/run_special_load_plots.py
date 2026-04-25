"""Stage: run_special_load_plots — ethanol-equivalent + machine scenario PNGs."""
from __future__ import annotations

from dataclasses import dataclass

from ..context import RuntimeContext


@dataclass(frozen=True)
class RunSpecialLoadPlotsStage:
    feature_key: str = "run_special_load_plots"

    def run(self, ctx: RuntimeContext) -> None:
        if ctx.final_table is None:
            print("[INFO] run_special_load_plots | final_table is None; skipping.")
            return
        if ctx.output_dir is None:
            raise RuntimeError("run_special_load_plots requires ctx.output_dir to be set.")

        from ..special_load_plots import (
            plot_ethanol_equivalent_consumption_overlay,
            plot_ethanol_equivalent_ratio,
            plot_machine_scenario_suite,
        )

        plot_dir = ctx.output_dir / "plots"
        plot_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        p1 = plot_ethanol_equivalent_consumption_overlay(ctx.final_table, plot_dir=plot_dir)
        if p1 is not None:
            count += 1
        p2 = plot_ethanol_equivalent_ratio(ctx.final_table, plot_dir=plot_dir)
        if p2 is not None:
            count += 1
        count += plot_machine_scenario_suite(ctx.final_table, plot_dir=plot_dir)

        print(f"[OK] run_special_load_plots | {count} PNGs generated.")
