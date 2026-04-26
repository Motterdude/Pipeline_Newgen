"""Main dispatch loop for unitary plots.

Iterates ``plots_df`` rows, resolves columns and plot parameters, then
delegates to the appropriate renderer.  Port of legacy L8789-9142.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..final_table._helpers import _to_str_or_empty, norm_key, resolve_col
from .config_parsing import (
    _decorate_plot_variant_output,
    _derive_filename_for_expansion,
    _derive_title_for_expansion,
    _mapping_unit_for_y_col,
    _parse_axis_limits,
    _parse_axis_spec,
    _parse_axis_value,
    _parse_csv_list_ints,
    _plot_uncertainty_variants,
    _resolve_plot_x_request,
    _resolve_plot_yerr_col,
    _row_enabled,
    _runtime_plot_x_label,
    _safe_name,
    _shared_plot_y_limits_for_variants,
    _strip_leading_raw_plot_name,
    _to_float,
)
from .renderers import (
    plot_all_fuels,
    plot_all_fuels_delta_ref,
    plot_all_fuels_with_value_labels,
    plot_all_fuels_xy,
)
from ..sweep_axis import (
    resolve_plot_fixed_x_for_sweep,
    rewrite_plot_filename_title,
)


def _new_plot_run_summary() -> Dict[str, object]:
    return {
        "generated": 0,
        "skipped": 0,
        "disabled": 0,
        "generated_files": [],
        "generated_labels": [],
        "skipped_items": [],
    }


def make_plots_from_config_with_summary(
    out_df: pd.DataFrame,
    plots_df: pd.DataFrame,
    mappings: dict,
    plot_dir: Optional[Path] = None,
    series_col: Optional[str] = None,
    *,
    sweep_active: bool = False,
    sweep_x_col: str = "",
    sweep_effective_x_col: str = "",
    sweep_axis_label: str = "",
    sweep_axis_token: str = "",
) -> Dict[str, object]:
    summary = _new_plot_run_summary()
    target_dir = Path(plot_dir) if plot_dir is not None else Path("plots")

    def mark_generated(label: str, filename_value: str) -> None:
        summary["generated"] = int(summary.get("generated", 0)) + 1
        summary.setdefault("generated_labels", []).append(label)
        if filename_value:
            summary.setdefault("generated_files", []).append(
                str((target_dir / filename_value).resolve())
            )

    def mark_skipped(label: str, reason: str) -> None:
        summary["skipped"] = int(summary.get("skipped", 0)) + 1
        summary.setdefault("skipped_items", []).append((label, reason))

    if plots_df is None or plots_df.empty:
        print("[WARN] Plots config vazio; nao gerei plots via planilha.")
        return summary

    for _, r in plots_df.iterrows():
        if not _row_enabled(r.get("enabled", 0)):
            summary["disabled"] = int(summary.get("disabled", 0)) + 1
            continue

        plot_type = _to_str_or_empty(r.get("plot_type", ""))
        filename = _strip_leading_raw_plot_name(r.get("filename", ""))
        title = _strip_leading_raw_plot_name(r.get("title", ""))
        plot_label = (
            filename
            or title
            or _to_str_or_empty(r.get("y_col", ""))
            or _to_str_or_empty(r.get("plot_type", ""))
            or "plot_sem_nome"
        )

        if not plot_type:
            print("[ERROR] Plots row invalida: plot_type vazio. Pulei.")
            mark_skipped(plot_label, "plot_type vazio")
            continue

        x_col_req = _to_str_or_empty(r.get("x_col", ""))
        y_col_req = _to_str_or_empty(r.get("y_col", ""))
        x_label = _to_str_or_empty(r.get("x_label", ""))
        y_label = _to_str_or_empty(r.get("y_label", ""))

        y_axis_unit = _mapping_unit_for_y_col(y_col_req, mappings)
        fixed_x = _parse_axis_spec(
            r.get("x_min", pd.NA), r.get("x_max", pd.NA), r.get("x_step", pd.NA)
        )
        fixed_y = _parse_axis_spec(
            r.get("y_min", pd.NA),
            r.get("y_max", pd.NA),
            r.get("y_step", pd.NA),
            target_unit=y_axis_unit,
        )
        fixed_y_limits = _parse_axis_limits(
            r.get("y_min", pd.NA),
            r.get("y_max", pd.NA),
            target_unit=y_axis_unit,
        )
        y_tick_step = _parse_axis_value(
            r.get("y_step", pd.NA), target_unit=y_axis_unit, default=np.nan
        )
        if not np.isfinite(y_tick_step) or y_tick_step <= 0:
            y_tick_step = None
        if fixed_y is not None:
            y_tick_step = None
        y_tol_plus = _to_float(r.get("y_tol_plus", r.get("tol_plus", 0.0)), 0.0)
        y_tol_minus = _to_float(r.get("y_tol_minus", r.get("tol_minus", 0.0)), 0.0)

        fuels = _parse_csv_list_ints(r.get("filter_h2o_list", pd.NA))
        fuels_override = fuels if fuels is not None else None
        label_variant = _to_str_or_empty(r.get("label_variant", "box")).lower() or "box"
        pt = plot_type.lower().strip()

        sweep_kw = dict(
            sweep_active=sweep_active,
            sweep_x_col=sweep_x_col,
            sweep_effective_x_col=sweep_effective_x_col,
            sweep_axis_label=sweep_axis_label,
            sweep_axis_token=sweep_axis_token,
        )

        # ── kibox_all ───────────────────────────────────────────────
        if pt in {"kibox_all", "all_kibox"}:
            _dispatch_kibox_all(
                out_df, r, pt, filename, title, plot_label,
                x_col_req, x_label, y_label,
                fixed_x, fixed_y, fixed_y_limits, y_tick_step,
                y_tol_plus, y_tol_minus, fuels_override, series_col,
                plot_dir, mark_generated, mark_skipped, sweep_kw,
            )
            continue

        # ── all_fuels_yx / all_fuels ────────────────────────────────
        if pt in {"all_fuels_yx", "all_fuels", "all_fuels_y_vs_x"}:
            _dispatch_all_fuels(
                out_df, r, mappings, filename, title, plot_label,
                x_col_req, y_col_req, x_label, y_label,
                fixed_x, fixed_y, fixed_y_limits, y_tick_step,
                y_tol_plus, y_tol_minus, fuels_override, series_col,
                plot_dir, mark_generated, mark_skipped, sweep_kw,
            )
            continue

        # ── all_fuels_xy / xy ───────────────────────────────────────
        if pt in {"all_fuels_xy", "xy"}:
            _dispatch_all_fuels_xy(
                out_df, r, mappings, filename, title, plot_label,
                x_col_req, y_col_req, x_label, y_label,
                fixed_x, fixed_y, fixed_y_limits, y_tick_step,
                y_tol_plus, y_tol_minus, fuels_override, series_col,
                plot_dir, mark_generated, mark_skipped, sweep_kw,
            )
            continue

        # ── all_fuels_labels / labels ───────────────────────────────
        if pt in {"all_fuels_labels", "labels"}:
            _dispatch_labels(
                out_df, r, filename, title, plot_label,
                x_col_req, y_col_req, x_label, y_label, label_variant,
                fixed_x, fixed_y, fixed_y_limits, y_tick_step,
                y_tol_plus, y_tol_minus, fuels_override, series_col,
                plot_dir, mark_generated, mark_skipped, sweep_kw,
            )
            continue

        # ── all_fuels_delta_ref / delta_ref ────────────────────────
        if pt in {"all_fuels_delta_ref", "delta_ref"}:
            _dispatch_delta_ref(
                out_df, r, mappings, filename, title, plot_label,
                x_col_req, y_col_req, x_label, y_label,
                fixed_x, fixed_y, fixed_y_limits, y_tick_step,
                y_tol_plus, y_tol_minus, fuels_override, series_col,
                plot_dir, mark_generated, mark_skipped, sweep_kw,
            )
            continue

        print(f"[ERROR] Plot '{filename or title}': plot_type '{plot_type}' nao suportado. Pulei.")
        mark_skipped(plot_label, f"plot_type nao suportado: {plot_type}")

    print(
        f"[OK] Plots-config: {int(summary.get('generated', 0))} gerados; "
        f"{int(summary.get('skipped', 0))} pulados; "
        f"{int(summary.get('disabled', 0))} desabilitados."
    )
    return summary


# ── dispatch helpers ────────────────────────────────────────────────

def _dispatch_kibox_all(
    out_df, r, pt, filename, title, plot_label,
    x_col_req, x_label, y_label,
    fixed_x, fixed_y, fixed_y_limits, y_tick_step,
    y_tol_plus, y_tol_minus, fuels_override, series_col,
    plot_dir, mark_generated, mark_skipped, sweep_kw,
):
    kibox_cols = [c for c in out_df.columns if str(c).startswith("KIBOX_") and c != "KIBOX_N_files"]
    if not kibox_cols:
        print("[WARN] kibox_all: nao ha colunas KIBOX_* no output. Pulei expansao.")
        mark_skipped(plot_label, "sem colunas KIBOX_* no output")
        return

    sw = sweep_kw or {}
    x_resolve_kw = {k: sw.get(k, "") for k in ("sweep_active", "sweep_x_col", "sweep_effective_x_col")}
    x_label_kw = {k: sw.get(k, "") for k in ("sweep_active", "sweep_x_col", "sweep_effective_x_col", "sweep_axis_label")}

    x_col_base, mestrado_x_override = _resolve_plot_x_request(x_col_req, **x_resolve_kw)
    try:
        x_col = resolve_col(out_df, x_col_base)
    except Exception as e:
        print(f"[ERROR] kibox_all: x_col '{x_col_base}' nao encontrado. Pulei expansao. ({e})")
        mark_skipped(plot_label, f"x_col ausente: {x_col_base}")
        return

    xlab = _runtime_plot_x_label(x_label, x_col_base, x_col, mestrado_x_override, **x_label_kw)
    eff_fixed_x = resolve_plot_fixed_x_for_sweep(
        x_col_req, fixed_x,
        sweep_active=sw.get("sweep_active", False),
        sweep_x_col=sw.get("sweep_x_col", ""),
    ) if sw.get("sweep_active") else fixed_x

    seen_filenames: set = set()
    for yc in sorted(kibox_cols):
        fn = _derive_filename_for_expansion(filename, yc)
        fn_key = norm_key(fn)
        item_label = fn or yc
        if fn_key in seen_filenames:
            print(f"[INFO] kibox_all: filename duplicado apos normalizacao ('{fn}'). Pulei a expansao de '{yc}'.")
            mark_skipped(item_label, "filename duplicado apos normalizacao")
            continue
        seen_filenames.add(fn_key)
        tt = _derive_title_for_expansion(title, x_col=x_col, y_col=yc)
        if sw.get("sweep_active"):
            fn, tt = rewrite_plot_filename_title(
                fn, tt, x_col_req=x_col_req, x_col_resolved=x_col,
                sweep_active=True, sweep_x_col=sw.get("sweep_x_col", ""),
                sweep_effective_x_col=sw.get("sweep_effective_x_col", ""),
                sweep_axis_token=sw.get("sweep_axis_token", ""),
                sweep_axis_label=sw.get("sweep_axis_label", ""),
            )
        ylab = y_label if y_label else yc
        ok = plot_all_fuels(
            out_df, y_col=yc, yerr_col=None, title=tt, filename=fn,
            y_label=ylab, fixed_y=fixed_y, fixed_y_limits=fixed_y_limits,
            y_tick_step=y_tick_step, fixed_x=eff_fixed_x, x_col=x_col,
            x_label=xlab, fuels_override=fuels_override,
            series_col=series_col, plot_dir=plot_dir,
            y_tol_plus=y_tol_plus, y_tol_minus=y_tol_minus,
        )
        if ok:
            mark_generated(item_label, fn)
        else:
            mark_skipped(item_label, "sem dados validos para plot")


def _dispatch_all_fuels(
    out_df, r, mappings, filename, title, plot_label,
    x_col_req, y_col_req, x_label, y_label,
    fixed_x, fixed_y, fixed_y_limits, y_tick_step,
    y_tol_plus, y_tol_minus, fuels_override, series_col,
    plot_dir, mark_generated, mark_skipped, sweep_kw,
):
    sw = sweep_kw or {}
    x_resolve_kw = {k: sw.get(k, "") for k in ("sweep_active", "sweep_x_col", "sweep_effective_x_col")}
    x_label_kw = {k: sw.get(k, "") for k in ("sweep_active", "sweep_x_col", "sweep_effective_x_col", "sweep_axis_label")}

    x_col_base, mestrado_x_override = _resolve_plot_x_request(x_col_req, **x_resolve_kw)
    try:
        x_col = resolve_col(out_df, x_col_base)
    except Exception as e:
        print(f"[ERROR] Plot '{filename or title}': x_col '{x_col_base}' nao encontrado. Pulei. ({e})")
        mark_skipped(plot_label, f"x_col ausente: {x_col_base}")
        return
    if not y_col_req:
        print(f"[ERROR] Plot '{filename or title}': y_col vazio. Pulei.")
        mark_skipped(plot_label, "y_col vazio")
        return
    try:
        y_col = resolve_col(out_df, y_col_req)
    except Exception as e:
        print(f"[ERROR] Plot '{filename or title}': y_col '{y_col_req}' nao encontrado. Pulei. ({e})")
        mark_skipped(plot_label, f"y_col ausente: {y_col_req}")
        return

    x_label = _runtime_plot_x_label(x_label, x_col_base, x_col, mestrado_x_override, **x_label_kw)
    if not y_label:
        y_label = y_col
    if not title:
        title = f"{y_col} vs {x_col} (all fuels)"
    if not filename:
        filename = f"{_safe_name(y_col)}_vs_{_safe_name(x_col)}_all.png"

    if sw.get("sweep_active"):
        filename, title = rewrite_plot_filename_title(
            filename, title, x_col_req=x_col_req, x_col_resolved=x_col,
            sweep_active=True, sweep_x_col=sw.get("sweep_x_col", ""),
            sweep_effective_x_col=sw.get("sweep_effective_x_col", ""),
            sweep_axis_token=sw.get("sweep_axis_token", ""),
            sweep_axis_label=sw.get("sweep_axis_label", ""),
        )
    eff_fixed_x = resolve_plot_fixed_x_for_sweep(
        x_col_req, fixed_x,
        sweep_active=sw.get("sweep_active", False),
        sweep_x_col=sw.get("sweep_x_col", ""),
    ) if sw.get("sweep_active") else fixed_x

    variant_specs: List[Tuple[str, str, Optional[str], str]] = []
    for variant_key, uncertainty_mode, dual_variant in _plot_uncertainty_variants(r):
        variant_row = r.copy()
        variant_row["show_uncertainty"] = uncertainty_mode
        variant_filename, variant_title = _decorate_plot_variant_output(
            filename, title, variant_key, dual_variant
        )
        yerr_col = _resolve_plot_yerr_col(
            out_df, variant_row, y_col=y_col, mappings=mappings,
            plot_label=variant_filename or variant_title or y_col,
        )
        variant_specs.append((variant_filename, variant_title, yerr_col, variant_key))

    variant_fixed_y_limits = fixed_y_limits
    if fixed_y is None and fixed_y_limits is None and len(variant_specs) > 1:
        shared_limits = _shared_plot_y_limits_for_variants(
            out_df, x_col=x_col, y_col=y_col,
            variant_yerr_cols=[spec[2] for spec in variant_specs],
            fuels_override=fuels_override, series_col=series_col,
            y_tol_plus=y_tol_plus, y_tol_minus=y_tol_minus,
        )
        if shared_limits is not None:
            variant_fixed_y_limits = shared_limits

    for variant_filename, variant_title, yerr_col, _variant_key in variant_specs:
        item_label = variant_filename or variant_title or plot_label
        ok = plot_all_fuels(
            out_df, y_col=y_col, yerr_col=yerr_col, title=variant_title,
            filename=variant_filename, y_label=y_label, fixed_y=fixed_y,
            fixed_y_limits=variant_fixed_y_limits, y_tick_step=y_tick_step,
            fixed_x=eff_fixed_x, x_col=x_col, x_label=x_label,
            fuels_override=fuels_override, series_col=series_col,
            plot_dir=plot_dir, y_tol_plus=y_tol_plus, y_tol_minus=y_tol_minus,
        )
        if ok:
            mark_generated(item_label, variant_filename)
        else:
            mark_skipped(item_label, "sem dados validos para plot")


def _dispatch_all_fuels_xy(
    out_df, r, mappings, filename, title, plot_label,
    x_col_req, y_col_req, x_label, y_label,
    fixed_x, fixed_y, fixed_y_limits, y_tick_step,
    y_tol_plus, y_tol_minus, fuels_override, series_col,
    plot_dir, mark_generated, mark_skipped, sweep_kw,
):
    if not y_col_req:
        print(f"[ERROR] Plot '{filename or title}': y_col vazio (plot_type=all_fuels_xy). Pulei.")
        mark_skipped(plot_label, "y_col vazio")
        return

    sw = sweep_kw or {}
    x_resolve_kw = {k: sw.get(k, "") for k in ("sweep_active", "sweep_x_col", "sweep_effective_x_col")}
    x_label_kw = {k: sw.get(k, "") for k in ("sweep_active", "sweep_x_col", "sweep_effective_x_col", "sweep_axis_label")}

    x_col_base, mestrado_x_override = _resolve_plot_x_request(x_col_req, **x_resolve_kw)
    try:
        x_col = resolve_col(out_df, x_col_base)
    except Exception as e:
        print(f"[ERROR] Plot '{filename or title}': x_col '{x_col_base}' nao encontrado. Pulei. ({e})")
        mark_skipped(plot_label, f"x_col ausente: {x_col_base}")
        return
    try:
        y_col = resolve_col(out_df, y_col_req)
    except Exception as e:
        print(f"[ERROR] Plot '{filename or title}': y_col '{y_col_req}' nao encontrado. Pulei. ({e})")
        mark_skipped(plot_label, f"y_col ausente: {y_col_req}")
        return

    x_label = _runtime_plot_x_label(x_label, x_col_base, x_col, mestrado_x_override, **x_label_kw)
    if not y_label:
        y_label = y_col
    if not title:
        title = f"{y_col} vs {x_col} (all fuels)"
    if not filename:
        filename = f"{_safe_name(y_col)}_vs_{_safe_name(x_col)}_all.png"

    if sw.get("sweep_active"):
        filename, title = rewrite_plot_filename_title(
            filename, title, x_col_req=x_col_req, x_col_resolved=x_col,
            sweep_active=True, sweep_x_col=sw.get("sweep_x_col", ""),
            sweep_effective_x_col=sw.get("sweep_effective_x_col", ""),
            sweep_axis_token=sw.get("sweep_axis_token", ""),
            sweep_axis_label=sw.get("sweep_axis_label", ""),
        )
    eff_fixed_x = resolve_plot_fixed_x_for_sweep(
        x_col_req, fixed_x,
        sweep_active=sw.get("sweep_active", False),
        sweep_x_col=sw.get("sweep_x_col", ""),
    ) if sw.get("sweep_active") else fixed_x

    variant_specs: List[Tuple[str, str, Optional[str], str]] = []
    for variant_key, uncertainty_mode, dual_variant in _plot_uncertainty_variants(r):
        variant_row = r.copy()
        variant_row["show_uncertainty"] = uncertainty_mode
        variant_filename, variant_title = _decorate_plot_variant_output(
            filename, title, variant_key, dual_variant
        )
        yerr_col = _resolve_plot_yerr_col(
            out_df, variant_row, y_col=y_col, mappings=mappings,
            plot_label=variant_filename or variant_title or y_col,
        )
        variant_specs.append((variant_filename, variant_title, yerr_col, variant_key))

    variant_fixed_y_limits = fixed_y_limits
    if fixed_y is None and fixed_y_limits is None and len(variant_specs) > 1:
        shared_limits = _shared_plot_y_limits_for_variants(
            out_df, x_col=x_col, y_col=y_col,
            variant_yerr_cols=[spec[2] for spec in variant_specs],
            fuels_override=fuels_override, series_col=series_col,
            y_tol_plus=y_tol_plus, y_tol_minus=y_tol_minus,
        )
        if shared_limits is not None:
            variant_fixed_y_limits = shared_limits

    for variant_filename, variant_title, yerr_col, _variant_key in variant_specs:
        item_label = variant_filename or variant_title or plot_label
        ok = plot_all_fuels_xy(
            out_df, x_col=x_col, y_col=y_col, yerr_col=yerr_col,
            title=variant_title, filename=variant_filename,
            x_label=x_label, y_label=y_label, fixed_y=fixed_y,
            fixed_y_limits=variant_fixed_y_limits, y_tick_step=y_tick_step,
            fixed_x=eff_fixed_x, fuels_override=fuels_override,
            series_col=series_col, plot_dir=plot_dir,
            y_tol_plus=y_tol_plus, y_tol_minus=y_tol_minus,
        )
        if ok:
            mark_generated(item_label, variant_filename)
        else:
            mark_skipped(item_label, "sem dados validos para plot")


def _dispatch_labels(
    out_df, r, filename, title, plot_label,
    x_col_req, y_col_req, x_label, y_label, label_variant,
    fixed_x, fixed_y, fixed_y_limits, y_tick_step,
    y_tol_plus, y_tol_minus, fuels_override, series_col,
    plot_dir, mark_generated, mark_skipped, sweep_kw,
):
    sw = sweep_kw or {}
    x_resolve_kw = {k: sw.get(k, "") for k in ("sweep_active", "sweep_x_col", "sweep_effective_x_col")}
    x_label_kw = {k: sw.get(k, "") for k in ("sweep_active", "sweep_x_col", "sweep_effective_x_col", "sweep_axis_label")}

    x_col_base, mestrado_x_override = _resolve_plot_x_request(x_col_req, **x_resolve_kw)
    try:
        x_col = resolve_col(out_df, x_col_base)
    except Exception as e:
        print(f"[ERROR] Plot '{filename or title}': x_col '{x_col_base}' nao encontrado. Pulei. ({e})")
        mark_skipped(plot_label, f"x_col ausente: {x_col_base}")
        return
    if not y_col_req:
        print(f"[ERROR] Plot '{filename or title}': y_col vazio (plot_type=all_fuels_labels). Pulei.")
        mark_skipped(plot_label, "y_col vazio")
        return
    try:
        y_col = resolve_col(out_df, y_col_req)
    except Exception as e:
        print(f"[ERROR] Plot '{filename or title}': y_col '{y_col_req}' nao encontrado. Pulei. ({e})")
        mark_skipped(plot_label, f"y_col ausente: {y_col_req}")
        return

    x_label = _runtime_plot_x_label(x_label, x_col_base, x_col, mestrado_x_override, **x_label_kw)
    if not y_label:
        y_label = y_col
    if not title:
        title = f"{y_col} vs {x_col} (labels)"
    if not filename:
        filename = f"{_safe_name(y_col)}_vs_{_safe_name(x_col)}_labels.png"

    if sw.get("sweep_active"):
        filename, title = rewrite_plot_filename_title(
            filename, title, x_col_req=x_col_req, x_col_resolved=x_col,
            sweep_active=True, sweep_x_col=sw.get("sweep_x_col", ""),
            sweep_effective_x_col=sw.get("sweep_effective_x_col", ""),
            sweep_axis_token=sw.get("sweep_axis_token", ""),
            sweep_axis_label=sw.get("sweep_axis_label", ""),
        )
    eff_fixed_x = resolve_plot_fixed_x_for_sweep(
        x_col_req, fixed_x,
        sweep_active=sw.get("sweep_active", False),
        sweep_x_col=sw.get("sweep_x_col", ""),
    ) if sw.get("sweep_active") else fixed_x

    ok = plot_all_fuels_with_value_labels(
        out_df, y_col=y_col, title=title, filename=filename,
        y_label=y_label, label_variant=label_variant,
        fixed_y=fixed_y, fixed_y_limits=fixed_y_limits,
        y_tick_step=y_tick_step, fixed_x=eff_fixed_x,
        x_col=x_col, x_label=x_label,
        fuels_override=fuels_override, series_col=series_col,
        plot_dir=plot_dir, y_tol_plus=y_tol_plus, y_tol_minus=y_tol_minus,
    )
    if ok:
        mark_generated(filename or plot_label, filename)
    else:
        mark_skipped(filename or plot_label, "sem dados validos para plot")


def _dispatch_delta_ref(
    out_df, r, mappings, filename, title, plot_label,
    x_col_req, y_col_req, x_label, y_label,
    fixed_x, fixed_y, fixed_y_limits, y_tick_step,
    y_tol_plus, y_tol_minus, fuels_override, series_col,
    plot_dir, mark_generated, mark_skipped, sweep_kw,
):
    sw = sweep_kw or {}
    x_resolve_kw = {k: sw.get(k, "") for k in ("sweep_active", "sweep_x_col", "sweep_effective_x_col")}
    x_label_kw = {k: sw.get(k, "") for k in ("sweep_active", "sweep_x_col", "sweep_effective_x_col", "sweep_axis_label")}

    x_col_base, mestrado_x_override = _resolve_plot_x_request(x_col_req, **x_resolve_kw)
    try:
        x_col = resolve_col(out_df, x_col_base)
    except Exception as e:
        print(f"[ERROR] Plot '{filename or title}': x_col '{x_col_base}' nao encontrado. Pulei. ({e})")
        mark_skipped(plot_label, f"x_col ausente: {x_col_base}")
        return
    if not y_col_req:
        print(f"[ERROR] Plot '{filename or title}': y_col vazio. Pulei.")
        mark_skipped(plot_label, "y_col vazio")
        return
    try:
        y_col = resolve_col(out_df, y_col_req)
    except Exception as e:
        print(f"[ERROR] Plot '{filename or title}': y_col '{y_col_req}' nao encontrado. Pulei. ({e})")
        mark_skipped(plot_label, f"y_col ausente: {y_col_req}")
        return

    y_col_delta = _to_str_or_empty(r.get("y_col_delta", ""))
    yerr_delta = _to_str_or_empty(r.get("yerr_delta", ""))
    y_label_delta = _to_str_or_empty(r.get("y_label_delta", ""))
    ref_fuel = _to_str_or_empty(r.get("ref_fuel", "D85B15")) or "D85B15"

    x_label = _runtime_plot_x_label(x_label, x_col_base, x_col, mestrado_x_override, **x_label_kw)
    if not y_label:
        y_label = y_col
    if not y_label_delta:
        y_label_delta = f"Delta vs {ref_fuel}"
    if not title:
        title = f"{y_col} vs {x_col} — Delta vs {ref_fuel}"
    if not filename:
        filename = f"{_safe_name(y_col)}_vs_{_safe_name(x_col)}_delta_ref.png"

    if sw.get("sweep_active"):
        filename, title = rewrite_plot_filename_title(
            filename, title, x_col_req=x_col_req, x_col_resolved=x_col,
            sweep_active=True, sweep_x_col=sw.get("sweep_x_col", ""),
            sweep_effective_x_col=sw.get("sweep_effective_x_col", ""),
            sweep_axis_token=sw.get("sweep_axis_token", ""),
            sweep_axis_label=sw.get("sweep_axis_label", ""),
        )
    eff_fixed_x = resolve_plot_fixed_x_for_sweep(
        x_col_req, fixed_x,
        sweep_active=sw.get("sweep_active", False),
        sweep_x_col=sw.get("sweep_x_col", ""),
    ) if sw.get("sweep_active") else fixed_x

    variant_specs: List[Tuple[str, str, Optional[str], str]] = []
    for variant_key, uncertainty_mode, dual_variant in _plot_uncertainty_variants(r):
        variant_row = r.copy()
        variant_row["show_uncertainty"] = uncertainty_mode
        variant_filename, variant_title = _decorate_plot_variant_output(
            filename, title, variant_key, dual_variant
        )
        yerr_col = _resolve_plot_yerr_col(
            out_df, variant_row, y_col=y_col, mappings=mappings,
            plot_label=variant_filename or variant_title or y_col,
        )
        variant_specs.append((variant_filename, variant_title, yerr_col, variant_key))

    for variant_filename, variant_title, yerr_col, _variant_key in variant_specs:
        item_label = variant_filename or variant_title or plot_label
        ok = plot_all_fuels_delta_ref(
            out_df, y_col=y_col, y_col_delta=y_col_delta,
            yerr_col=yerr_col, yerr_col_delta=yerr_delta or None,
            title=variant_title, filename=variant_filename,
            y_label=y_label, y_label_delta=y_label_delta,
            ref_fuel=ref_fuel,
            fixed_y=fixed_y, fixed_y_limits=fixed_y_limits,
            y_tick_step=y_tick_step, fixed_x=eff_fixed_x,
            x_col=x_col, x_label=x_label,
            fuels_override=fuels_override, series_col=series_col,
            plot_dir=plot_dir, y_tol_plus=y_tol_plus, y_tol_minus=y_tol_minus,
        )
        if ok:
            mark_generated(item_label, variant_filename)
        else:
            mark_skipped(item_label, "sem dados validos para plot")
