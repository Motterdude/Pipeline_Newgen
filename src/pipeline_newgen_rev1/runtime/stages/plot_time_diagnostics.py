"""Stage: time-diagnostics plots (plotting phase only).

Reads ``ctx.time_diagnostics`` (populated by ``RunTimeDiagnosticsStage`` in the
processing phase) and generates the ~20 PNGs under ``ctx.output_dir/plots/``.
No computation happens here — only rendering.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..context import RuntimeContext
from ..time_diagnostics import (
    plot_time_delta_all_samples,
    plot_time_delta_by_file,
)


@dataclass(frozen=True)
class PlotTimeDiagnosticsStage:
    feature_key: str = "plot_time_diagnostics"

    def run(self, ctx: RuntimeContext) -> None:
        if ctx.time_diagnostics is None or ctx.time_diagnostics.empty:
            print("[INFO] plot_time_diagnostics | no diagnostics data; skipping.")
            return
        if ctx.output_dir is None:
            print("[INFO] plot_time_diagnostics | output_dir is None; skipping.")
            return

        plot_dir = ctx.output_dir / "plots"
        plot_dir.mkdir(parents=True, exist_ok=True)
        try:
            all_samples_png = plot_time_delta_all_samples(ctx.time_diagnostics, plot_dir=plot_dir)
            per_file_count = plot_time_delta_by_file(ctx.time_diagnostics, plot_dir=plot_dir)
            print(
                f"[OK] plot_time_diagnostics | plots: all_samples={'1' if all_samples_png else '0'}, "
                f"per_file={per_file_count}"
            )
        except Exception as exc:
            print(f"[WARN] plot_time_diagnostics | plot generation failed: {type(exc).__name__}: {exc}")
