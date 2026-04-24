"""Native ``build_final_table`` stage — replaces ``BuildFinalTableBridgeStage``."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..context import RuntimeContext


@dataclass(frozen=True)
class BuildFinalTableStage:
    feature_key: str = "build_final_table"

    def run(self, ctx: RuntimeContext) -> None:
        if ctx.ponto is None:
            print("[INFO] build_final_table | ponto is None; skipping.")
            return
        if ctx.bundle is None:
            print("[INFO] build_final_table | bundle is None; skipping.")
            return

        from ..final_table import build_final_table

        ctx.final_table = build_final_table(
            ponto=ctx.ponto,
            fuel_properties=ctx.fuel_properties if ctx.fuel_properties is not None else pd.DataFrame(),
            kibox_agg=ctx.kibox_agg if ctx.kibox_agg is not None else pd.DataFrame(),
            motec_ponto=ctx.motec_ponto if ctx.motec_ponto is not None else pd.DataFrame(),
            mappings=ctx.bundle.mappings,
            instruments=ctx.bundle.instruments,
            reporting=ctx.bundle.reporting,
            defaults=ctx.bundle.defaults,
        )
        rows = len(ctx.final_table) if ctx.final_table is not None else 0
        print(f"[OK] build_final_table | rows={rows}")
