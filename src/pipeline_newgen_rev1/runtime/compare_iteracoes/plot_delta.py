"""Renderer: delta-percentage comparison plot (single curve with error bars + 0% line)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


def plot_compare_delta_pct(
    delta_df: pd.DataFrame,
    *,
    metric_id: str,
    left_id: str,
    right_id: str,
    variant_key: str,
    value_name: str,
    title: str,
    filename: str,
    target_dir: Path,
    label_line: str,
    note_text: str,
    include_uncertainty: bool = True,
) -> Optional[Path]:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print(f"[WARN] plot_compare_delta_pct | matplotlib not available; skipping {filename}.")
        return None

    if delta_df is None or delta_df.empty:
        return None

    mask = (
        delta_df["label_left"].eq(
            delta_df["label_left"].iloc[0] if not delta_df.empty else ""
        )
    )
    rows = delta_df
    if "Metrica" in delta_df.columns and "Comparacao" in delta_df.columns:
        from .specs import COMPARE_ITER_METRIC_SPECS_BY_ID, compare_iter_pair_context
        spec = COMPARE_ITER_METRIC_SPECS_BY_ID.get(metric_id, {})
        pair_ctx = compare_iter_pair_context(left_id, right_id)
        suffix = "" if variant_key == "with_uncertainty" else f" ({variant_key})"
        expected_metrica = spec.get("title", "")
        expected_comp = pair_ctx["pair_title"] + suffix
        rows = delta_df[
            delta_df["Metrica"].eq(expected_metrica) & delta_df["Comparacao"].eq(expected_comp)
        ].copy()

    if rows.empty:
        return None

    m = rows.sort_values("Load_kW")

    plt.figure()
    if include_uncertainty and m["U_delta_pct"].notna().any():
        plt.errorbar(
            m["Load_kW"], m["delta_pct"], yerr=m["U_delta_pct"],
            fmt="o-", capsize=3, linewidth=1.8, markersize=4.5, color="#2ca02c", label=label_line,
        )
    else:
        plt.plot(m["Load_kW"], m["delta_pct"], "o-", linewidth=1.8, markersize=4.5, color="#2ca02c", label=label_line)

    plt.axhline(0.0, color="gray", linestyle="--", linewidth=1.0, label="0%")
    plt.xlabel("Carga nominal (kW)")
    plt.ylabel("Delta percentual (%)")
    plt.title(title)
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.legend()
    plt.gcf().text(0.01, 0.01, note_text, fontsize=8, alpha=0.85)
    outpath = target_dir / filename
    plt.tight_layout()
    plt.savefig(outpath, dpi=200)
    plt.close()
    return outpath
