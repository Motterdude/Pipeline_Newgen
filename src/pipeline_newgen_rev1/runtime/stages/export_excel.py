"""Native ``export_excel`` stage — writes ctx.final_table to lv_kpis_clean.xlsx."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..context import RuntimeContext
from ..plot_point_filter import apply_plot_point_filter


_LV_KPIS_FILENAME = "lv_kpis_clean.xlsx"


@dataclass(frozen=True)
class ExportExcelStage:
    feature_key: str = "export_excel"

    def run(self, ctx: RuntimeContext) -> None:
        if ctx.final_table is None:
            print("[INFO] export_excel | final_table is None; skipping.")
            return
        if ctx.output_dir is None:
            raise RuntimeError("export_excel requires ctx.output_dir to be resolved first.")

        df = ctx.final_table
        if isinstance(getattr(ctx, "selected_plot_points", None), set) and ctx.selected_plot_points:
            df = apply_plot_point_filter(df, ctx.selected_plot_points)
            n_removed = len(ctx.final_table) - len(df)
            if n_removed > 0:
                print(f"[INFO] export_excel | plot_point_filter removed {n_removed} rows from export")

        target = Path(ctx.output_dir) / _LV_KPIS_FILENAME
        try:
            df.to_excel(target, index=False)
            ctx.lv_kpis_path = target
        except PermissionError:
            ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            alt = target.with_name(f"{target.stem}_{ts}{target.suffix}")
            df.to_excel(alt, index=False)
            ctx.lv_kpis_path = alt
            print(f"[WARN] export_excel | arquivo bloqueado, salvei em {alt.name}")

        rows = len(df)
        cols = len(df.columns)
        print(f"[OK] export_excel | wrote {ctx.lv_kpis_path} ({rows}x{cols})")
