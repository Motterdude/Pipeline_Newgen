"""Plot relative uncertainty of absolute (L/h) vs specific (g/kWh) fuel consumption.

Reads the last exported lv_kpis_clean.xlsx (default: E:\\out_Nanum\\lv_kpis_clean.xlsx),
and renders three comparison plots into a tempdir:
  1) U_rel_Consumo_L_h vs Load_kW, one line per Fuel_Label
  2) U_rel_BSFC_g_kWh vs Load_kW, one line per Fuel_Label
  3) value ± U errorbar for both metrics, twin-axis

Relative uncertainty is U_* / value * 100 (%).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


DEFAULT_INPUT = Path(r"E:\out_Nanum\lv_kpis_clean.xlsx")


def load_kpis(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    if "Consumo_kg_h" not in df.columns and "Consumo_kg_h_mean_of_windows" in df.columns:
        df["Consumo_kg_h"] = df["Consumo_kg_h_mean_of_windows"]
    keep = [
        "BaseName", "Fuel_Label", "Load_kW",
        "Consumo_kg_h", "U_Consumo_kg_h", "uc_Consumo_kg_h",
        "uA_Consumo_kg_h", "uB_Consumo_kg_h",
        "Consumo_L_h", "U_Consumo_L_h", "uc_Consumo_L_h",
        "uA_Consumo_L_h", "uB_Consumo_L_h",
        "BSFC_g_kWh", "U_BSFC_g_kWh", "uc_BSFC_g_kWh",
        "uA_BSFC_g_kWh", "uB_BSFC_g_kWh",
        "Fuel_Density_kg_m3",
    ]
    keep = [c for c in keep if c in df.columns]
    out = df[keep].copy()
    for c in out.columns:
        if c not in ("BaseName", "Fuel_Label"):
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out.dropna(subset=["Load_kW", "Consumo_L_h", "BSFC_g_kWh"]).reset_index(drop=True)


def load_compare_iteracoes(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_excel(path)
    # Keep only consumo, media vs media (the cleanest BL vs ADTV view).
    mask = (df["Metrica"].str.lower() == "consumo") & (df["Comparacao"].str.contains("media"))
    return df[mask].copy().sort_values("Load_kW").reset_index(drop=True)


def _rel(u, v):
    return (u / v) * 100.0


def plot_relative_uncertainties(df: pd.DataFrame, out_dir: Path) -> list[Path]:
    df = df.copy()
    df["U_rel_L_h_pct"] = _rel(df["U_Consumo_L_h"], df["Consumo_L_h"])
    df["U_rel_BSFC_pct"] = _rel(df["U_BSFC_g_kWh"], df["BSFC_g_kWh"])
    df["U_rel_kg_h_pct"] = _rel(df["U_Consumo_kg_h"], df["Consumo_kg_h"])

    fuels = sorted(df["Fuel_Label"].dropna().unique().tolist())
    cmap = plt.get_cmap("tab10")
    colors = {f: cmap(i % 10) for i, f in enumerate(fuels)}

    artifacts: list[Path] = []

    # (1) relative U: L/h vs BSFC on the same plot
    fig, ax = plt.subplots(figsize=(10, 6))
    for fuel in fuels:
        g = df[df["Fuel_Label"] == fuel].sort_values("Load_kW")
        c = colors[fuel]
        ax.plot(g["Load_kW"], g["U_rel_L_h_pct"],
                marker="o", linestyle="-", color=c,
                label=f"{fuel} — Consumo L/h")
        ax.plot(g["Load_kW"], g["U_rel_BSFC_pct"],
                marker="s", linestyle="--", color=c, alpha=0.7,
                label=f"{fuel} — BSFC g/kWh")
    ax.set_xlabel("Load_kW")
    ax.set_ylabel("Incerteza expandida relativa  U/valor  [%]")
    ax.set_title("Incerteza relativa (k=2) — consumo absoluto L/h vs específico g/kWh")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, ncol=2, loc="best")
    p = out_dir / "u_relativa_consumo_vs_bsfc.png"
    fig.tight_layout()
    fig.savefig(p, dpi=140)
    plt.close(fig)
    artifacts.append(p)

    # (2) absolute values with errorbars — L/h
    fig, ax = plt.subplots(figsize=(10, 6))
    for fuel in fuels:
        g = df[df["Fuel_Label"] == fuel].sort_values("Load_kW")
        ax.errorbar(g["Load_kW"], g["Consumo_L_h"], yerr=g["U_Consumo_L_h"],
                    fmt="o-", color=colors[fuel], label=fuel, capsize=3)
    ax.set_xlabel("Load_kW")
    ax.set_ylabel("Consumo  [L/h]")
    ax.set_title("Consumo absoluto ± U (k=2)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)
    p = out_dir / "consumo_l_h_errorbar.png"
    fig.tight_layout()
    fig.savefig(p, dpi=140)
    plt.close(fig)
    artifacts.append(p)

    # (3) absolute values with errorbars — BSFC
    fig, ax = plt.subplots(figsize=(10, 6))
    for fuel in fuels:
        g = df[df["Fuel_Label"] == fuel].sort_values("Load_kW")
        ax.errorbar(g["Load_kW"], g["BSFC_g_kWh"], yerr=g["U_BSFC_g_kWh"],
                    fmt="s-", color=colors[fuel], label=fuel, capsize=3)
    ax.set_xlabel("Load_kW")
    ax.set_ylabel("BSFC  [g/kWh]")
    ax.set_title("Consumo específico ± U (k=2)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)
    p = out_dir / "bsfc_errorbar.png"
    fig.tight_layout()
    fig.savefig(p, dpi=140)
    plt.close(fig)
    artifacts.append(p)

    # (4) decomposition: uA vs uB contribution for both metrics
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=False)
    for ax, metric, value_col, ua_col, ub_col, ylabel in [
        (axes[0], "Consumo L/h", "Consumo_L_h", "uA_Consumo_L_h", "uB_Consumo_L_h", "contrib. relativa [%]"),
        (axes[1], "BSFC g/kWh", "BSFC_g_kWh", "uA_BSFC_g_kWh", "uB_BSFC_g_kWh", "contrib. relativa [%]"),
    ]:
        for fuel in fuels:
            g = df[df["Fuel_Label"] == fuel].sort_values("Load_kW")
            ax.plot(g["Load_kW"], _rel(g[ua_col], g[value_col]),
                    marker="o", linestyle="-", color=colors[fuel],
                    label=f"{fuel} — uA/valor")
            ax.plot(g["Load_kW"], _rel(g[ub_col], g[value_col]),
                    marker="^", linestyle=":", color=colors[fuel], alpha=0.7,
                    label=f"{fuel} — uB/valor")
        ax.set_xlabel("Load_kW")
        ax.set_ylabel(ylabel)
        ax.set_title(f"uA vs uB (relativo) — {metric}")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7, ncol=2)
    p = out_dir / "decomposicao_uA_vs_uB.png"
    fig.tight_layout()
    fig.savefig(p, dpi=140)
    plt.close(fig)
    artifacts.append(p)

    return artifacts


def plot_compare_iteracoes(cmp_df: pd.DataFrame, out_dir: Path) -> list[Path]:
    if cmp_df.empty:
        return []
    artifacts: list[Path] = []

    # Left/right values with errorbars (BL vs ADTV), plus delta_pct ± U_delta_pct.
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    ax = axes[0]
    ax.errorbar(cmp_df["Load_kW"], cmp_df["value_left"], yerr=cmp_df["U_left"],
                fmt="o-", color="tab:blue", label=f"{cmp_df['label_left'].iloc[0]} (BL)", capsize=3)
    ax.errorbar(cmp_df["Load_kW"], cmp_df["value_right"], yerr=cmp_df["U_right"],
                fmt="s-", color="tab:red", label=f"{cmp_df['label_right'].iloc[0]} (ADTV)", capsize=3)
    ax.set_xlabel("Load_kW")
    ax.set_ylabel("consumo (legado: unidade da métrica)")
    ax.set_title("BL vs ADTV — consumo ± U (k=2)")
    ax.grid(True, alpha=0.3)
    ax.legend()

    ax = axes[1]
    ax.errorbar(cmp_df["Load_kW"], cmp_df["delta_pct"], yerr=cmp_df["U_delta_pct"],
                fmt="D-", color="tab:purple", capsize=3)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Load_kW")
    ax.set_ylabel("delta_pct  [%]")
    ax.set_title("Δ = (ADTV/BL − 1)·100 ± U_delta_pct (k=2)")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    p = out_dir / "bl_vs_adtv_consumo_delta.png"
    fig.savefig(p, dpi=140)
    plt.close(fig)
    artifacts.append(p)

    # Relative uncertainty: absolute (U_left/value_left) vs delta (U_delta_pct)
    rel_left = (cmp_df["U_left"] / cmp_df["value_left"]) * 100
    rel_right = (cmp_df["U_right"] / cmp_df["value_right"]) * 100
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(cmp_df["Load_kW"], rel_left, "o-", color="tab:blue", label="U_rel BL [%]")
    ax.plot(cmp_df["Load_kW"], rel_right, "s-", color="tab:red", label="U_rel ADTV [%]")
    ax.plot(cmp_df["Load_kW"], cmp_df["U_delta_pct"], "D--", color="tab:purple",
            label="U_delta_pct [%]  (já é relativo)")
    ax.set_xlabel("Load_kW")
    ax.set_ylabel("incerteza expandida relativa [%]")
    ax.set_title("Incerteza relativa: absoluto (BL, ADTV) × delta_pct")
    ax.grid(True, alpha=0.3)
    ax.legend()
    p = out_dir / "u_relativa_absoluto_vs_delta.png"
    fig.tight_layout()
    fig.savefig(p, dpi=140)
    plt.close(fig)
    artifacts.append(p)
    return artifacts


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for fuel, g in df.groupby("Fuel_Label"):
        rows.append({
            "Fuel_Label": fuel,
            "N_points": len(g),
            "U_rel_kg_h_pct_mean": float(_rel(g["U_Consumo_kg_h"], g["Consumo_kg_h"]).mean()),
            "U_rel_kg_h_pct_max": float(_rel(g["U_Consumo_kg_h"], g["Consumo_kg_h"]).max()),
            "U_rel_L_h_pct_mean": float(_rel(g["U_Consumo_L_h"], g["Consumo_L_h"]).mean()),
            "U_rel_L_h_pct_max": float(_rel(g["U_Consumo_L_h"], g["Consumo_L_h"]).max()),
            "U_rel_BSFC_pct_mean": float(_rel(g["U_BSFC_g_kWh"], g["BSFC_g_kWh"]).mean()),
            "U_rel_BSFC_pct_max": float(_rel(g["U_BSFC_g_kWh"], g["BSFC_g_kWh"]).max()),
            "U_rel_BSFC_pct_min": float(_rel(g["U_BSFC_g_kWh"], g["BSFC_g_kWh"]).min()),
        })
    return pd.DataFrame(rows).sort_values("Fuel_Label").reset_index(drop=True)


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    if not src.exists():
        print(f"[ERR] input not found: {src}")
        return 2
    out_dir = Path(tempfile.mkdtemp(prefix="uncertainty_plots_"))
    print(f"[plot] input: {src}")
    print(f"[plot] out_dir: {out_dir}")
    df = load_kpis(src)
    print(f"[plot] loaded {len(df)} points, fuels = {sorted(df['Fuel_Label'].dropna().unique())}")

    summary = summarize(df)
    print("\n=== resumo U relativa (k=2) por combustivel ===")
    print(summary.to_string(index=False))
    summary.to_csv(out_dir / "summary.csv", index=False)

    artifacts = plot_relative_uncertainties(df, out_dir)

    # Also plot BL vs ADTV delta from compare_iteracoes_metricas_incertezas.xlsx.
    cmp_path = src.parent / "plots" / "compare_iteracoes_bl_vs_adtv" / "compare_iteracoes_metricas_incertezas.xlsx"
    cmp_df = load_compare_iteracoes(cmp_path)
    if not cmp_df.empty:
        print(f"\n[plot] compare_iteracoes rows (consumo, media): {len(cmp_df)}")
        rel_left_mean = ((cmp_df['U_left']/cmp_df['value_left']).mean())*100
        rel_right_mean = ((cmp_df['U_right']/cmp_df['value_right']).mean())*100
        u_delta_mean = cmp_df['U_delta_pct'].mean()
        print(f"[plot] U_rel BL médio:   {rel_left_mean:.2f} %")
        print(f"[plot] U_rel ADTV médio: {rel_right_mean:.2f} %")
        print(f"[plot] U_delta_pct médio: {u_delta_mean:.2f} %")
        print(f"[plot] |delta_pct| médio: {cmp_df['delta_pct'].abs().mean():.2f} %")
        print(f"[plot] delta_over_U médio: {cmp_df['delta_over_U'].abs().mean():.2f}")
        artifacts += plot_compare_iteracoes(cmp_df, out_dir)

    print("\n[plot] artefatos:")
    for a in artifacts:
        print(f"  {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
