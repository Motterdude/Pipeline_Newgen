"""Replot absolute and delta_pct of the fuel consumption comparison with
BL=blue, ADTV=red, solid lines; delta in green with errorbar (GUM §5, k=2);
autoscale y-axis with ticks every 1 %; and an interpretation footnote that
explicitly states the sign convention (negative = better consumption).

Writes into
  C:\\Users\\sc61730\\AppData\\Local\\Temp\\legacy_n_th_compare_ugioh2ya\\
    out\\plots\\compare_iteracoes_bl_vs_adtv\\

6 PNGs (3 ramps × {absolute, delta}).
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
METRIC_TITLE = "Consumo"
Y_LABEL_ABS = "Consumo [kg/h]"
NOTE_DELTA = (
    "Negativo = melhor consumo no aditivado (consome menos que baseline); "
    "Positivo = pior consumo (consome mais que baseline)"
)

BL_COLOR = "tab:blue"
ADTV_COLOR = "tab:red"
DELTA_COLOR = "tab:green"


def _autoscale_step(lo: float, hi: float, step: float = 1.0, pad: float = 0.5) -> tuple[float, float, np.ndarray]:
    lo_i = np.floor((lo - pad) / step) * step
    hi_i = np.ceil((hi + pad) / step) * step
    ticks = np.arange(lo_i, hi_i + 1e-9, step)
    return float(lo_i), float(hi_i), ticks


def _propagate_delta(g: pd.DataFrame) -> pd.DataFrame:
    """uc_delta_pct via GUM §5 from uc per side — same rule the fixed legacy uses."""
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


def plot_absolute(
    g: pd.DataFrame, label_left: str, label_right: str, out_path: Path,
    y_lim: tuple[float, float], y_ticks: np.ndarray,
) -> None:
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

    ax.set_ylim(*y_lim)
    ax.set_yticks(y_ticks)
    ax.set_xlabel("Carga nominal (kW)")
    ax.set_ylabel(Y_LABEL_ABS)
    ax.set_title(f"Compare {label_left} vs {label_right} - {METRIC_TITLE}")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5)
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
        fmt="D-", color=DELTA_COLOR,
        label="δ% consumo (negativo = melhor, positivo = pior)",
        capsize=3, markersize=6, linewidth=1.8,
    )
    ax.axhline(0.0, color="gray", linestyle="--", linewidth=1.0, label="0% = sem diferença")

    ax.set_ylim(*y_lim)
    ax.set_yticks(y_ticks)
    ax.set_xlabel("Carga nominal (kW)")
    ax.set_ylabel("Delta percentual (%)")
    ax.set_title(f"Compare {label_left} vs {label_right} - {METRIC_TITLE} - Delta percentual")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5)
    ax.legend(loc="best", fontsize=9)
    fig.text(0.01, 0.01, NOTE_DELTA, fontsize=8, alpha=0.85)
    fig.tight_layout(); fig.savefig(out_path, dpi=200); plt.close(fig)


def _shared_scale_absolute(consumo: pd.DataFrame) -> tuple[tuple[float, float], np.ndarray]:
    """Union of (value ± U) across all 3 ramp comparisons, snapped to step 2."""
    df = consumo.copy()
    for c in ("value_left", "U_left", "value_right", "U_right"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    lows  = pd.concat([df["value_left"] - df["U_left"], df["value_right"] - df["U_right"]]).dropna()
    highs = pd.concat([df["value_left"] + df["U_left"], df["value_right"] + df["U_right"]]).dropna()
    lo_i, hi_i, ticks = _autoscale_step(float(lows.min()), float(highs.max()), step=2.0)
    return (lo_i, hi_i), ticks


def _shared_scale_delta(consumo: pd.DataFrame) -> tuple[tuple[float, float], np.ndarray]:
    """Union of (delta ± U_delta) across all 3 ramps, snapped to step 2."""
    all_delta_lo, all_delta_hi = [], []
    for _cmp, g in consumo.groupby("Comparacao"):
        gp = _propagate_delta(g)
        all_delta_lo.extend((gp["delta_pct"] - gp["U_delta_pct"]).dropna().tolist())
        all_delta_hi.extend((gp["delta_pct"] + gp["U_delta_pct"]).dropna().tolist())
    lo_i, hi_i, ticks = _autoscale_step(min(all_delta_lo), max(all_delta_hi), step=2.0)
    return (lo_i, hi_i), ticks


def main() -> int:
    tempdir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TEMPDIR
    report = tempdir / "out" / "plots" / "compare_iteracoes_bl_vs_adtv" / "compare_iteracoes_metricas_incertezas.xlsx"
    out_dir = tempdir / "out" / "plots" / "compare_iteracoes_bl_vs_adtv"

    if not report.exists():
        print(f"[ERR] report not found: {report}")
        return 2
    df = pd.read_excel(report)
    consumo = df[df["Metrica"].str.lower() == "consumo"].copy()
    if consumo.empty:
        print("[ERR] no consumo rows found in report.")
        return 1

    print(f"[replot] report: {report}")
    print(f"[replot] out_dir: {out_dir}")
    print(f"[replot] consumo rows: {len(consumo)}")

    # Shared y-axis scales across the 3 ramps (step 2, autoscale by union of envelopes)
    abs_ylim, abs_ticks = _shared_scale_absolute(consumo[consumo["Comparacao"].isin(COMPARISONS)])
    delta_ylim, delta_ticks = _shared_scale_delta(consumo[consumo["Comparacao"].isin(COMPARISONS)])
    print(f"[replot] shared abs y-scale: {abs_ylim}, ticks at {list(abs_ticks)}")
    print(f"[replot] shared delta y-scale: {delta_ylim}, ticks at {list(delta_ticks)}")

    summary = []
    for cmp, g in consumo.groupby("Comparacao"):
        if cmp not in COMPARISONS:
            continue
        slug, label_left, label_right = COMPARISONS[cmp]

        abs_path = out_dir / f"compare_iteracoes_{cmp}_consumo_abs_autoscale.png"
        plot_absolute(g, label_left, label_right, abs_path, abs_ylim, abs_ticks)
        print(f"  wrote {abs_path.name}")

        delta_path = out_dir / f"compare_iteracoes_{cmp}_consumo_abs_autoscale_delta_pct.png"
        plot_delta(g, label_left, label_right, delta_path, delta_ylim, delta_ticks)
        print(f"  wrote {delta_path.name}")

        gp = _propagate_delta(g)
        summary.append({
            "comparacao": cmp,
            "N_pontos": int(gp["delta_pct"].notna().sum()),
            "delta_pct_min": float(gp["delta_pct"].min()),
            "delta_pct_max": float(gp["delta_pct"].max()),
            "|delta|_mean": float(gp["delta_pct"].abs().mean()),
            "U_delta_pct_mean": float(gp["U_delta_pct"].mean()),
            "U_delta_pct_max":  float(gp["U_delta_pct"].max()),
            "|delta|/U_mean":   float((gp["delta_pct"].abs() / gp["U_delta_pct"]).mean()),
            "n_significativos_95pct": int((gp["delta_pct"].abs() > gp["U_delta_pct"]).sum()),
        })

    print("\n=== resumo delta consumo por rampa (U propagado GUM, k=2) ===")
    print(pd.DataFrame(summary).round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
