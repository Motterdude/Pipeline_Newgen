"""Stage: validate and enrich sweep metadata on all frames.

The readers (labview_reader, motec_reader, kibox_reader) already populate
Sweep_Key, Sweep_Value, Sweep_Display_Label on every row from the
InputFileMeta produced by input_discovery.  This stage:
  1. Sets ctx.sweep_active based on aggregation_mode.
  2. Fills missing Sweep_Key with the runtime-selected key.
  3. Logs a diagnostic summary.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..context import RuntimeContext


@dataclass(frozen=True)
class ParseSweepMetadataStage:
    feature_key: str = "parse_sweep_metadata"

    def run(self, ctx: RuntimeContext) -> None:
        sel = ctx.normalized_state.selection if ctx.normalized_state else None
        if sel is None or sel.aggregation_mode != "sweep":
            ctx.sweep_active = False
            return

        ctx.sweep_active = True
        runtime_key = sel.sweep_key

        all_frames = ctx.labview_frames + ctx.motec_frames
        total_rows = sum(len(f) for f in all_frames)
        rows_with_key = 0

        for f in all_frames:
            if "Sweep_Key" not in f.columns:
                continue
            valid = f["Sweep_Key"].notna() & f["Sweep_Key"].astype(str).str.strip().ne("")
            rows_with_key += int(valid.sum())
            missing = ~valid
            if missing.any():
                f.loc[missing, "Sweep_Key"] = runtime_key

        print(
            f"[OK] parse_sweep_metadata | sweep_active=True, key={runtime_key}, "
            f"rows_with_sweep={rows_with_key}/{total_rows}"
        )
