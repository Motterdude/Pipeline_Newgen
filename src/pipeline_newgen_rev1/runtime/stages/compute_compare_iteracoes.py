"""Stage: compute compare_iteracoes deltas (processing phase).

Reads ``ctx.final_table`` and ``ctx.bundle.compare_df`` to compute per-metric
aggregation, series frames, and delta tables with GUM uncertainty propagation.
Exports ``compare_iteracoes_metricas_incertezas.xlsx`` and populates
``ctx.compare_iteracoes_*`` fields for the downstream plotting stage.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..context import RuntimeContext


@dataclass(frozen=True)
class ComputeCompareIteracoesStage:
    feature_key: str = "compute_compare_iteracoes"

    def run(self, ctx: RuntimeContext) -> None:
        if ctx.final_table is None:
            print("[INFO] compute_compare_iteracoes | final_table is None; skipping.")
            return
        if ctx.bundle is None:
            print("[INFO] compute_compare_iteracoes | bundle is None; skipping.")
            return

        from ..compare_iteracoes.core import compute_compare_iteracoes

        compare_df = getattr(ctx.bundle, "compare_df", None)
        mappings = getattr(ctx.bundle, "mappings", {})

        pairs_override = None
        if ctx.compare_iter_pairs_override:
            import json
            try:
                pairs_override = json.loads(ctx.compare_iter_pairs_override)
            except (json.JSONDecodeError, TypeError) as exc:
                print(f"[WARN] compute_compare_iteracoes | invalid --compare-iter-pairs JSON: {exc}")

        result = compute_compare_iteracoes(
            ctx.final_table, compare_df, mappings,
            pairs_override=pairs_override,
            catalog=ctx.campaign_catalog,
        )
        ctx.compare_iteracoes_table = result.delta_table
        ctx.compare_iteracoes_series = result.series_by_metric
        ctx.compare_iteracoes_requests = result.requests

        if ctx.output_dir is not None and not result.delta_table.empty:
            import pandas as _pd

            target_dir = ctx.output_dir / "plots" / "compare_iteracoes_bl_vs_adtv"
            target_dir.mkdir(parents=True, exist_ok=True)
            xlsx_path = target_dir / "compare_iteracoes_metricas_incertezas.xlsx"
            try:
                result.delta_table.to_excel(xlsx_path, index=False)
                ctx.compare_iteracoes_export_path = xlsx_path
                print(f"[OK] compute_compare_iteracoes | wrote {xlsx_path.name} ({len(result.delta_table)} rows)")
            except PermissionError:
                alt = xlsx_path.with_stem(xlsx_path.stem + "_new")
                result.delta_table.to_excel(alt, index=False)
                ctx.compare_iteracoes_export_path = alt
                print(f"[WARN] compute_compare_iteracoes | permission error → wrote {alt.name}")

            # Also embed compare data as a second sheet in lv_kpis_clean.xlsx so the
            # Preview Plot auto-detects it on a single Browse without a separate file.
            lv_kpis_path = getattr(ctx, "lv_kpis_path", None)
            if lv_kpis_path and lv_kpis_path.exists():
                try:
                    with _pd.ExcelWriter(
                        lv_kpis_path, engine="openpyxl", mode="a",
                        if_sheet_exists="replace",
                    ) as writer:
                        result.delta_table.to_excel(writer, sheet_name="compare", index=False)
                    print(
                        f"[OK] compute_compare_iteracoes | embedded 'compare' sheet in {lv_kpis_path.name}"
                    )
                except Exception as exc:
                    print(f"[WARN] compute_compare_iteracoes | could not embed compare sheet: {exc}")
        elif result.delta_table.empty:
            print("[INFO] compute_compare_iteracoes | no delta rows produced (no enabled comparisons?).")
