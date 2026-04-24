"""Stage: native trechos/ponto aggregation.

Consumes ``ctx.labview_frames`` (populated by ``_discover_and_read_inputs``
in the runner) and ``ctx.bundle.instruments``. Produces ``ctx.trechos`` and
``ctx.ponto``, which downstream stages (``build_final_table``, etc.) consume.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..context import RuntimeContext
from ..trechos_ponto import compute_ponto_stats, compute_trechos_stats


@dataclass(frozen=True)
class ComputeTrechosPontoStage:
    feature_key: str = "compute_trechos_ponto"

    def run(self, ctx: RuntimeContext) -> None:
        if not ctx.labview_frames:
            print("[INFO] compute_trechos_ponto | labview_frames empty; skipping.")
            return

        lv_raw = pd.concat(ctx.labview_frames, ignore_index=True)
        instruments = ctx.bundle.instruments if ctx.bundle is not None else []

        try:
            trechos = compute_trechos_stats(lv_raw, instruments=instruments)
        except KeyError as exc:
            print(f"[WARN] compute_trechos_ponto | {exc}; skipping.")
            return
        ponto = compute_ponto_stats(trechos)

        ctx.trechos = trechos
        ctx.ponto = ponto
        print(f"[OK] compute_trechos_ponto | trechos={len(trechos)} rows, ponto={len(ponto)} rows")
