"""Native stage: generate the KPEAK exceedance distribution plots."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..context import RuntimeContext
from ..fuel_colors import fuel_color_map
from ..knock_histogram import plot_knock_exceedance_pct, plot_knock_cycle_count


def _load_tag(load_kw: float) -> str:
    if load_kw == int(load_kw):
        return f"{int(load_kw)}kW"
    return f"{load_kw}kW"


def _generate_set(data, plot_dir: Path, tag: str, colors: dict) -> None:
    """Generate the 3 plot variants for a given dataset + tag."""
    plot_knock_exceedance_pct(
        data, plot_dir / f"knock_kpeak_exceedance_distribution_{tag}.png",
        title=f"KPEAK Exceedance — {tag} (all fuels)",
        fuel_colors=colors,
    )
    plot_knock_cycle_count(
        data, plot_dir / f"knock_kpeak_cycle_count_{tag}.png",
        title=f"KPEAK Exceedance — Cycle Count — {tag}",
        y_scale="linear", fuel_colors=colors,
    )
    plot_knock_cycle_count(
        data, plot_dir / f"knock_kpeak_cycle_count_log2_{tag}.png",
        title=f"KPEAK Exceedance — Cycle Count — {tag}",
        y_scale="log2", fuel_colors=colors,
    )


@dataclass(frozen=True)
class PlotKnockHistogramStage:
    feature_key: str = "plot_knock_histogram"

    def run(self, ctx: RuntimeContext) -> None:
        if not ctx.knock_histogram_raw:
            print("[INFO] plot_knock_histogram | no KPEAK data collected; skipping.")
            return
        if ctx.output_dir is None:
            print("[WARN] plot_knock_histogram | output_dir is None; skipping.")
            return

        defaults = ctx.bundle.defaults if ctx.bundle is not None else {}
        all_fuel_labels = list(ctx.knock_histogram_raw.keys())
        colors = fuel_color_map(all_fuel_labels, defaults=defaults)

        plot_dir = Path(ctx.output_dir) / "plots"
        plot_dir.mkdir(parents=True, exist_ok=True)

        total_cycles = sum(len(v) for v in ctx.knock_histogram_raw.values())
        total_fuels = len(ctx.knock_histogram_raw)
        print(
            f"[INFO] plot_knock_histogram | {total_fuels} fuel(s), "
            f"{total_cycles} total cycles"
        )

        _generate_set(ctx.knock_histogram_raw, plot_dir, "all", colors)

        n_loads = len(ctx.knock_histogram_by_load)
        if n_loads == 0:
            return
        print(f"[INFO] plot_knock_histogram | generating per-load plots for {n_loads} load(s)")

        for load_kw in sorted(ctx.knock_histogram_by_load):
            data_for_load = ctx.knock_histogram_by_load[load_kw]
            tag = _load_tag(load_kw)
            _generate_set(data_for_load, plot_dir, tag, colors)
