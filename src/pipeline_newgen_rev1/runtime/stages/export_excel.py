"""Native ``export_excel`` stage — writes ctx.final_table to lv_kpis_clean.xlsx."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..context import RuntimeContext


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

        target = Path(ctx.output_dir) / _LV_KPIS_FILENAME
        try:
            ctx.final_table.to_excel(target, index=False)
            ctx.lv_kpis_path = target
        except PermissionError:
            ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            alt = target.with_name(f"{target.stem}_{ts}{target.suffix}")
            ctx.final_table.to_excel(alt, index=False)
            ctx.lv_kpis_path = alt
            print(f"[WARN] export_excel | arquivo bloqueado, salvei em {alt.name}")

        rows = len(ctx.final_table)
        cols = len(ctx.final_table.columns)
        print(f"[OK] export_excel | wrote {ctx.lv_kpis_path} ({rows}x{cols})")
