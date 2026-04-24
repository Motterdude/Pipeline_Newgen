"""Stage: native time-diagnostics.

Consome `ctx.labview_frames` (preenchido por `_discover_and_read_inputs` no
runner), gera a tabela por amostra e o sumário por arquivo, escreve os 2
xlsx em `ctx.output_dir` e os PNGs em `ctx.output_dir/plots/`.

Este é o primeiro stage **nativo** pós-config — i.e. não depende do galpão
antigo. Os 19 PNGs em `time_delta_by_file/` + 1 `time_delta_to_next_all_samples.png`
que antes eram gerados só pelo legado passam a ser produzidos pelo newgen.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..context import RuntimeContext
from ..time_diagnostics import (
    build_time_diagnostics,
    plot_time_delta_all_samples,
    plot_time_delta_by_file,
    summarize_time_diagnostics,
)


@dataclass(frozen=True)
class RunTimeDiagnosticsStage:
    feature_key: str = "run_time_diagnostics"

    def run(self, ctx: RuntimeContext) -> None:
        if not ctx.labview_frames:
            print("[INFO] run_time_diagnostics | nothing to diagnose (labview_frames empty); skipping.")
            return
        if ctx.output_dir is None:
            print("[INFO] run_time_diagnostics | output_dir is None; skipping.")
            return

        lv_raw = pd.concat(ctx.labview_frames, ignore_index=True)
        quality_cfg = dict(ctx.bundle.data_quality) if ctx.bundle is not None else {}

        time_df = build_time_diagnostics(lv_raw, time_col="Time", quality_cfg=quality_cfg)
        if time_df.empty:
            print("[WARN] run_time_diagnostics | build_time_diagnostics retornou vazio (sem coluna Time?). Pulando.")
            return
        summary_df = summarize_time_diagnostics(time_df)

        ctx.time_diagnostics = time_df
        ctx.time_diagnostics_summary = summary_df

        out_dir = ctx.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        time_xlsx = out_dir / "lv_time_diagnostics.xlsx"
        summary_xlsx = out_dir / "lv_diagnostics_summay.xlsx"  # typo preserved from legacy
        try:
            time_df.to_excel(time_xlsx, index=False)
            summary_df.to_excel(summary_xlsx, index=False)
            print(f"[OK] run_time_diagnostics | wrote {time_xlsx.name} ({len(time_df)} rows)")
            print(f"[OK] run_time_diagnostics | wrote {summary_xlsx.name} ({len(summary_df)} rows)")
        except Exception as exc:
            print(f"[WARN] run_time_diagnostics | xlsx write failed: {type(exc).__name__}: {exc}")

        plot_dir = out_dir / "plots"
        plot_dir.mkdir(parents=True, exist_ok=True)
        try:
            all_samples_png = plot_time_delta_all_samples(time_df, plot_dir=plot_dir)
            per_file_count = plot_time_delta_by_file(time_df, plot_dir=plot_dir)
            print(
                f"[OK] run_time_diagnostics | plots: all_samples={'1' if all_samples_png else '0'}, "
                f"per_file={per_file_count}"
            )
        except Exception as exc:
            print(f"[WARN] run_time_diagnostics | plot generation failed: {type(exc).__name__}: {exc}")
