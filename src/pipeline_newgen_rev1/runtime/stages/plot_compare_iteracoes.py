"""Stage: compare_iteracoes plots (plotting phase only).

Reads ``ctx.compare_iteracoes_series`` and ``ctx.compare_iteracoes_requests``
(populated by ``ComputeCompareIteracoesStage``) and generates absolute-value
and delta-percentage PNGs.  No computation happens here — only rendering.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..context import RuntimeContext


@dataclass(frozen=True)
class PlotCompareIteracoesStage:
    feature_key: str = "plot_compare_iteracoes"

    def run(self, ctx: RuntimeContext) -> None:
        if ctx.compare_iteracoes_series is None or ctx.compare_iteracoes_requests is None:
            print("[INFO] plot_compare_iteracoes | no compare data; skipping.")
            return
        if ctx.output_dir is None:
            print("[INFO] plot_compare_iteracoes | output_dir is None; skipping.")
            return

        from ..compare_iteracoes.plot_absolute import plot_compare_absolute
        from ..compare_iteracoes.plot_delta import plot_compare_delta_pct
        from ..compare_iteracoes.specs import (
            COMPARE_ITER_METRIC_SPECS_BY_ID,
            compare_iter_pair_context,
        )

        target_dir = ctx.output_dir / "plots" / "compare_iteracoes_bl_vs_adtv"
        target_dir.mkdir(parents=True, exist_ok=True)

        png_count = 0
        for req in ctx.compare_iteracoes_requests:
            metric_id = req["metric_id"]
            spec = COMPARE_ITER_METRIC_SPECS_BY_ID.get(metric_id)
            if spec is None:
                continue
            series_for_metric = ctx.compare_iteracoes_series.get(metric_id)
            if series_for_metric is None:
                continue

            left_id = req["left_id"]
            right_id = req["right_id"]
            variant_key = req.get("variant_key", "with_uncertainty")
            include_uncertainty = req.get("show_uncertainty", "on") == "on"
            pair_ctx = compare_iter_pair_context(left_id, right_id)

            left_df = series_for_metric.get(left_id)
            right_df = series_for_metric.get(right_id)
            if left_df is None or right_df is None:
                continue

            value_name = spec["value_name"]
            suffix = "" if variant_key == "with_uncertainty" else f"_{variant_key}"
            slug = spec.get("filename_slug", metric_id)

            abs_path = plot_compare_absolute(
                left_df=left_df,
                right_df=right_df,
                value_name=value_name,
                y_label=spec.get("y_label", value_name),
                title=f"{spec.get('title', metric_id)} — {pair_ctx['pair_title']}",
                filename=f"compare_iteracoes_{pair_ctx['pair_slug']}_{slug}{suffix}.png",
                target_dir=target_dir,
                label_left=pair_ctx["left_label"],
                label_right=pair_ctx["right_label"],
                include_uncertainty=include_uncertainty,
            )
            if abs_path:
                png_count += 1

            dm = spec.get("delta_mode", "ratio")
            title_prefix = "Δ(pp)" if dm == "diff" else "Δ%"
            delta_path = plot_compare_delta_pct(
                delta_df=ctx.compare_iteracoes_table,
                metric_id=metric_id,
                left_id=left_id,
                right_id=right_id,
                variant_key=variant_key,
                value_name=value_name,
                title=f"{title_prefix} {spec.get('title', metric_id)} — {pair_ctx['pair_title']}",
                filename=f"compare_iteracoes_{pair_ctx['pair_slug']}_{slug}{suffix}_delta_pct.png",
                target_dir=target_dir,
                label_line=pair_ctx["line_label"],
                note_text=pair_ctx["note_text"],
                include_uncertainty=include_uncertainty,
                delta_mode=dm,
            )
            if delta_path:
                png_count += 1

        print(f"[OK] plot_compare_iteracoes | generated {png_count} PNGs in {target_dir.name}/")
