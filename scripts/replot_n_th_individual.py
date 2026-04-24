"""Replot η_th BL vs ADTV in 3 separate figures (subida, descida, média),
plus 3 delta_pct figures with statistically correct uncertainty propagation.

Reads compare_iteracoes_metricas_incertezas.xlsx from the tempdir given on
the CLI (default: legacy_n_th_compare_ugioh2ya) and writes 6 PNGs into the
same compare_iteracoes_bl_vs_adtv/ folder — alongside the legacy's own
native output PNGs.

Color convention: BL = blue, ADTV = red.
Lines: solid for both sides in the absolute plot.

Delta propagation (GUM §5):
  δ%               = 100 · (ADTV/BL − 1)
  ∂δ/∂ADTV         = 100 / BL
  ∂δ/∂BL           = −100 · ADTV / BL²
  uc_δ%            = √((∂δ/∂ADTV · uc_ADTV)² + (∂δ/∂BL · uc_BL)²)
  U_δ%             = 2 · uc_δ%    (k = 2)

This mirrors the fix we landed in _build_compare_metric_delta_table
and matches the propagation the "consumo" delta uses — so the error bars
on the delta plots of η_th should behave the same way: shrink at mid/high
loads (where uc/value is smaller) and grow at low loads (where η_th is
small and the 1/BL amplifier is large).
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DEFAULT_TEMPDIR = Path(r"C:\Users\sc61730\AppData\Local\Temp\legacy_n_th_compare_ugioh2ya")
K_COVERAGE = 2.0

COMPARISONS = {
    "baseline_subida_vs_aditivado_subida":   ("subida",  "Baseline subida",  "Aditivado subida"),
    "baseline_descida_vs_aditivado_descida": ("descida", "Baseline descida", "Aditivado descida"),
    "baseline_media_vs_aditivado_media":     ("media",   "Baseline média",   "Aditivado média"),
}
METRIC_TITLE = "Eficiência térmica"

BL_COLOR = "tab:blue"
ADTV_COLOR = "tab:red"


def _autoscale_step(lo: float, hi: float, step: float = 1.0, pad: float = 0.5) -> tuple[float, float, np.ndarray]:
    """Expand limits outward, snap to a multiple of `step`, return ticks every `step`."""
    lo_i = np.floor((lo - pad) / step) * step
    hi_i = np.ceil((hi + pad) / step) * step
    ticks = np.arange(lo_i, hi_i + 1e-9, step)
    return float(lo_i), float(hi_i), ticks


def _propagate_delta(g: pd.DataFrame) -> pd.DataFrame:
    """Compute delta_pct + uc_delta_pct + U_delta_pct via GUM §5 from uc per side.

    Requires columns: value_left, value_right, uc_left, uc_right.
    Returns a frame with added columns: delta_pct, uc_delta_pct, U_delta_pct,
    d_delta_d_right, d_delta_d_left.
    """
    g = g.copy()
    for c in ("value_left", "value_right", "uc_left", "uc_right"):
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g["delta_pct"] = 100.0 * (g["value_right"] / g["value_left"] - 1.0)
    g["d_delta_d_right"] = 100.0 / g["value_left"]
    g["d_delta_d_left"] = -100.0 * g["value_right"] / (g["value_left"] ** 2)
    g["uc_delta_pct"] = (
        (g["d_delta_d_right"].abs() * g["uc_right"]) ** 2
        + (g["d_delta_d_left"].abs() * g["uc_left"]) ** 2
    ) ** 0.5
    g["U_delta_pct"] = K_COVERAGE * g["uc_delta_pct"]
    return g


ABS_YLIM = (8.0, 33.0)
ABS_YTICKS = np.arange(8.0, 33.0 + 1e-9, 2.0)


def plot_absolute(g: pd.DataFrame, label_left: str, label_right: str, out_path: Path) -> None:
    g = g.sort_values("Load_kW").copy()
    for c in ("value_left", "U_left", "value_right", "U_right"):
        g[c] = pd.to_numeric(g[c], errors="coerce")

    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    ax.errorbar(
        g["Load_kW"], g["value_left"], yerr=g["U_left"],
        fmt="o-", color=BL_COLOR, label=label_left,
        capsize=3, markersize=6, linewidth=1.8,
    )
    ax.errorbar(
        g["Load_kW"], g["value_right"], yerr=g["U_right"],
        fmt="s-", color=ADTV_COLOR, label=label_right,
        capsize=3, markersize=6, linewidth=1.8,
    )

    ax.set_ylim(*ABS_YLIM)
    ax.set_yticks(ABS_YTICKS)
    ax.set_xlabel("Load_kW")
    ax.set_ylabel("η_th  [%]")
    ax.set_title(f"Compare {label_left} vs {label_right} - {METRIC_TITLE}")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=10)
    fig.tight_layout(); fig.savefig(out_path, dpi=200); plt.close(fig)


def plot_delta(
    g: pd.DataFrame, label_left: str, label_right: str, out_path: Path,
    y_lim: tuple[float, float], y_ticks: np.ndarray,
) -> None:
    g = _propagate_delta(g).sort_values("Load_kW")

    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    ax.errorbar(
        g["Load_kW"], g["delta_pct"], yerr=g["U_delta_pct"],
        fmt="D-", color="tab:green", label=f"δ% = ({label_right}/{label_left} − 1)·100",
        capsize=3, markersize=6, linewidth=1.8,
    )
    ax.axhline(0.0, color="gray", linestyle="--", linewidth=1.0, label="0%")

    ax.set_ylim(*y_lim)
    ax.set_yticks(y_ticks)
    ax.set_xlabel("Carga nominal (kW)")
    ax.set_ylabel("Delta percentual (%)")
    ax.set_title(f"Compare {label_left} vs {label_right} - {METRIC_TITLE} - Delta percentual")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5)
    ax.legend(loc="best", fontsize=9)
    # Interpretation note — mirrors legacy style for consumo ("Negativo = economia;
    # Positivo = piora") but flipped for efficiency where positive = improvement.
    note_text = "Positivo = melhora de eficiencia no aditivado; Negativo = piora"
    fig.text(0.01, 0.01, note_text, fontsize=8, alpha=0.85)
    fig.tight_layout(); fig.savefig(out_path, dpi=200); plt.close(fig)


def _shared_scale_delta(n_th: pd.DataFrame) -> tuple[tuple[float, float], np.ndarray]:
    """Union of (delta ± U_delta) across all 3 ramps, snapped to step 2."""
    lows, highs = [], []
    for _cmp, g in n_th.groupby("Comparacao"):
        gp = _propagate_delta(g)
        lows.extend((gp["delta_pct"] - gp["U_delta_pct"]).dropna().tolist())
        highs.extend((gp["delta_pct"] + gp["U_delta_pct"]).dropna().tolist())
    lo_i, hi_i, ticks = _autoscale_step(min(lows), max(highs), step=2.0)
    return (lo_i, hi_i), ticks


def main() -> int:
    tempdir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TEMPDIR
    report = tempdir / "out" / "plots" / "compare_iteracoes_bl_vs_adtv" / "compare_iteracoes_metricas_incertezas.xlsx"
    out_dir = tempdir / "out" / "plots" / "compare_iteracoes_bl_vs_adtv"

    if not report.exists():
        print(f"[ERR] report not found: {report}")
        return 2
    df = pd.read_excel(report)
    n_th = df[df["Metrica"].str.lower() == "n_th"].copy()
    if n_th.empty:
        print("[ERR] no n_th rows found in report.")
        return 1

    print(f"[replot] report: {report}")
    print(f"[replot] out_dir: {out_dir}")
    print(f"[replot] n_th rows: {len(n_th)}")
    print(f"[replot] abs y-scale (fixed): {ABS_YLIM}, ticks {list(ABS_YTICKS)}")

    # Shared delta y-scale across the 3 ramps, step 2 (same pattern as consumo)
    delta_ylim, delta_ticks = _shared_scale_delta(n_th[n_th["Comparacao"].isin(COMPARISONS)])
    print(f"[replot] delta y-scale (shared): {delta_ylim}, ticks {list(delta_ticks)}")

    summary_rows = []
    for cmp, g in n_th.groupby("Comparacao"):
        if cmp not in COMPARISONS:
            continue
        slug, label_left, label_right = COMPARISONS[cmp]

        abs_path = out_dir / f"compare_iteracoes_{cmp}_n_th_pct_autoscale.png"
        plot_absolute(g, label_left, label_right, abs_path)
        print(f"  wrote {abs_path.name}")

        delta_path = out_dir / f"compare_iteracoes_{cmp}_n_th_pct_autoscale_delta_pct.png"
        plot_delta(g, label_left, label_right, delta_path, delta_ylim, delta_ticks)
        print(f"  wrote {delta_path.name}")

        # Summary stats for this ramp
        gp = _propagate_delta(g)
        summary_rows.append({
            "comparacao": cmp,
            "N_pontos": int(gp["delta_pct"].notna().sum()),
            "delta_pct_min":   float(gp["delta_pct"].min()),
            "delta_pct_max":   float(gp["delta_pct"].max()),
            "|delta|_mean":    float(gp["delta_pct"].abs().mean()),
            "U_delta_pct_mean": float(gp["U_delta_pct"].mean()),
            "U_delta_pct_max":  float(gp["U_delta_pct"].max()),
            "|delta|/U_mean":   float((gp["delta_pct"].abs() / gp["U_delta_pct"]).mean()),
            "n_significativos_95pct": int((gp["delta_pct"].abs() > gp["U_delta_pct"]).sum()),
        })

    print("\n=== resumo delta n_th por rampa (U propagado GUM, k=2) ===")
    print(pd.DataFrame(summary_rows).round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
