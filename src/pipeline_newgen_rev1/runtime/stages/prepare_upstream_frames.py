"""Stage: prepare the three upstream frames that feed build_final_table.

1. **Fuel properties** — from ConfigBundle (text config) + optional lhv.csv fallback.
2. **KiBox cross-file aggregation** — groupby across per-file means already in ctx.
3. **MoTeC trechos → ponto** — same pattern as LabVIEW trechos/ponto.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd

from ..context import RuntimeContext
from ..fuel_properties import load_fuel_properties
from ..motec_stats import compute_motec_ponto_stats, compute_motec_trechos_stats

KIBOX_GROUP_COLS = ["SourceFolder", "Load_kW", "DIES_pct", "BIOD_pct", "EtOH_pct", "H2O_pct"]


def _aggregate_kibox_cross_file(aggregate_rows: List[dict]) -> pd.DataFrame:
    rows = [r["aggregate_row"] for r in aggregate_rows if "aggregate_row" in r]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)

    kibox_cols = [c for c in df.columns if c.startswith("KIBOX_") and c != "KIBOX_N_files"]
    present_group_cols = [c for c in KIBOX_GROUP_COLS if c in df.columns]
    if not present_group_cols:
        return df

    numeric_group_cols = [c for c in present_group_cols if c not in ("SourceFolder",)]
    for c in numeric_group_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in kibox_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["KIBOX_N_files"] = pd.to_numeric(df.get("KIBOX_N_files", 1), errors="coerce").fillna(1)

    g = df.groupby(present_group_cols, dropna=False, sort=True)
    means = g[kibox_cols].mean(numeric_only=True)
    n_files = g["KIBOX_N_files"].sum().rename("KIBOX_N_files")
    out = pd.concat([means, n_files], axis=1).reset_index()
    return out


@dataclass(frozen=True)
class PrepareUpstreamFramesStage:
    feature_key: str = "prepare_upstream_frames"

    def run(self, ctx: RuntimeContext) -> None:
        self._prepare_fuel_properties(ctx)
        self._prepare_kibox_agg(ctx)
        self._prepare_motec_ponto(ctx)

    def _prepare_fuel_properties(self, ctx: RuntimeContext) -> None:
        if ctx.bundle is None:
            return
        lhv_path = None
        if ctx.bundle.text_dir is not None:
            candidate = ctx.bundle.text_dir.parent / "lhv.csv"
            if candidate.exists():
                lhv_path = candidate
        ctx.fuel_properties = load_fuel_properties(
            fuel_rows=ctx.bundle.fuel_properties,
            defaults=ctx.bundle.defaults,
            lhv_csv_path=lhv_path,
        )
        n = len(ctx.fuel_properties) if ctx.fuel_properties is not None else 0
        print(f"[OK] prepare_upstream_frames | fuel_properties={n} rows")

    def _prepare_kibox_agg(self, ctx: RuntimeContext) -> None:
        if not ctx.kibox_aggregate_rows:
            return
        ctx.kibox_agg = _aggregate_kibox_cross_file(ctx.kibox_aggregate_rows)
        n = len(ctx.kibox_agg) if ctx.kibox_agg is not None else 0
        print(f"[OK] prepare_upstream_frames | kibox_agg={n} rows")

    def _prepare_motec_ponto(self, ctx: RuntimeContext) -> None:
        if not ctx.motec_frames:
            return
        motec_raw = pd.concat(ctx.motec_frames, ignore_index=True)
        motec_trechos = compute_motec_trechos_stats(motec_raw)
        ctx.motec_ponto = compute_motec_ponto_stats(motec_trechos)
        n = len(ctx.motec_ponto) if ctx.motec_ponto is not None else 0
        print(f"[OK] prepare_upstream_frames | motec_ponto={n} rows")
