"""Evaluate the baseline_media vs aditivado_media NOx comparison.

Question being answered: "a comparação entre médias pega o viés do dia
de ensaio da BL_subida (2026-03-06) — quanto desse delta é aditivo e
quanto é dia?"

Reads:
  - compare_iteracoes_metricas_incertezas.xlsx  (the exported comparison)
  - the 4 raw campaign folders (to recompute BL_media and ADTV_media
    independently from the report and apply a day-bias correction)

Outputs:
  - CSV with all 4 campaign means + BL_media, BL_media_corrected,
    ADTV_media, delta_pct for (media as-is), (media with day-bias
    correction), (descida only — the clean comparison)
  - 2 PNGs:
      (1) delta_pct(Load) for 3 comparisons overlaid: subida, descida, media
          plus a dashed curve for the day-bias-corrected media
      (2) BL_subida ratio to BL_descida per load — the day-bias signature
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


RAW_ROOT = Path(r"E:\raw_pyton\raw_NANUM")
CAMPAIGNS = {
    "BL_subida":    RAW_ROOT / "Subindo_baseline_2",
    "BL_descida":   RAW_ROOT / "Descendo_baseline_2",
    "ADTV_subida":  RAW_ROOT / "subindo_aditivado_1",
    "ADTV_descida": RAW_ROOT / "descendo_aditivado_1",
}
COMPARE_XLSX = Path(r"E:\out_Nanum\plots\compare_iteracoes_bl_vs_adtv\compare_iteracoes_metricas_incertezas.xlsx")


def _parse_load(name: str):
    import re
    m = re.search(r"(\d+(?:[,\.]\d+)?)\s*[kK][wW]", name)
    return float(m.group(1).replace(",", ".")) if m else None


def _nox_mean(path: Path) -> float | None:
    try:
        df = pd.read_excel(path, engine="calamine")
    except Exception:
        return None
    for c in df.columns:
        if str(c).upper() == "NOX":
            s = pd.to_numeric(df[c], errors="coerce")
            return float(s.mean()) if s.notna().any() else None
    return None


def collect_nox() -> pd.DataFrame:
    rows = []
    for tag, folder in CAMPAIGNS.items():
        for xlsx in sorted(folder.glob("*.xlsx")):
            rows.append({
                "campaign": tag,
                "load_kw": _parse_load(xlsx.name),
                "nox_mean": _nox_mean(xlsx),
            })
    df = pd.DataFrame(rows).dropna(subset=["load_kw", "nox_mean"])
    # Pivot to one row per load with 4 columns
    piv = df.pivot_table(index="load_kw", columns="campaign", values="nox_mean").reset_index()
    return piv.sort_values("load_kw").reset_index(drop=True)


def read_report_deltas() -> pd.DataFrame:
    df = pd.read_excel(COMPARE_XLSX)
    nx = df[df["Metrica"].str.lower() == "nox"].copy()
    piv = nx.pivot_table(
        index="Load_kW",
        columns="Comparacao",
        values="delta_pct",
    ).reset_index()
    piv.columns.name = None
    return piv.sort_values("Load_kW").reset_index(drop=True)


def main() -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="media_eval_"))
    print(f"[eval] out_dir: {out_dir}")

    raw = collect_nox()
    print(f"[eval] loaded raw NOx means for {len(raw)} loads")

    # BL_media and ADTV_media computed from raw
    raw["BL_media_raw"]   = (raw["BL_subida"]   + raw["BL_descida"])   / 2
    raw["ADTV_media_raw"] = (raw["ADTV_subida"] + raw["ADTV_descida"]) / 2

    # Day-bias estimator: ratio BL_subida(Mar06) / BL_descida(Mar09) per load
    raw["day_bias_ratio"] = raw["BL_subida"] / raw["BL_descida"]

    # "Corrected" BL_subida: scale Mar06 data up to Mar09 reference using the
    # per-load (or median) ratio. Using the median across loads is more
    # robust to outlier points.
    median_ratio = raw["day_bias_ratio"].median()
    print(f"[eval] median day-bias ratio (BL_sub Mar06 / BL_des Mar09) = {median_ratio:.3f}")
    raw["BL_subida_corrected"] = raw["BL_subida"] / median_ratio
    raw["BL_media_corrected"]  = (raw["BL_subida_corrected"] + raw["BL_descida"]) / 2

    # Three deltas:
    raw["delta_pct_media_asis"]      = 100 * (raw["ADTV_media_raw"] / raw["BL_media_raw"] - 1)
    raw["delta_pct_media_corrected"] = 100 * (raw["ADTV_media_raw"] / raw["BL_media_corrected"] - 1)
    raw["delta_pct_descida_only"]    = 100 * (raw["ADTV_descida"]   / raw["BL_descida"]      - 1)
    raw["delta_pct_subida_only"]     = 100 * (raw["ADTV_subida"]    / raw["BL_subida"]       - 1)

    raw.to_csv(out_dir / "nox_campaigns_and_deltas.csv", index=False)

    # Cross-check: report deltas vs our recomputed ones
    rep = read_report_deltas()
    merged = raw.merge(
        rep.rename(columns={
            "baseline_subida_vs_aditivado_subida":   "report_delta_subida",
            "baseline_descida_vs_aditivado_descida": "report_delta_descida",
            "baseline_media_vs_aditivado_media":     "report_delta_media",
            "Load_kW":                                "load_kw",
        }),
        on="load_kw", how="left",
    )
    merged.to_csv(out_dir / "merged_report_vs_recomputed.csv", index=False)

    diff_subida  = (merged["delta_pct_subida_only"]  - merged["report_delta_subida"]).abs()
    diff_descida = (merged["delta_pct_descida_only"] - merged["report_delta_descida"]).abs()
    diff_media   = (merged["delta_pct_media_asis"]   - merged["report_delta_media"]).abs()
    print(f"[eval] |delta_pct recomputed - report| max: "
          f"subida={diff_subida.max():.3f}%, descida={diff_descida.max():.3f}%, "
          f"media={diff_media.max():.3f}% (tudo em unidade absoluta de pct)")

    # Summary table
    print("\n=== delta_pct por Load — 3 comparações + correção de viés de dia ===")
    cols_show = ["load_kw", "delta_pct_subida_only", "delta_pct_descida_only",
                 "delta_pct_media_asis", "delta_pct_media_corrected"]
    summary = raw[cols_show].copy()
    summary.columns = ["Load_kW", "delta_sub", "delta_des", "delta_media", "delta_media_corrigido"]
    print(summary.round(2).to_string(index=False))

    # Plot 1: four delta curves overlaid
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.plot(raw["load_kw"], raw["delta_pct_subida_only"],
            "^-", color="tab:red",    label="delta subida (contaminado por Mar 06)")
    ax.plot(raw["load_kw"], raw["delta_pct_descida_only"],
            "s-", color="tab:green",  label="delta descida (mesmo dia — OK)")
    ax.plot(raw["load_kw"], raw["delta_pct_media_asis"],
            "o-", color="tab:purple", label="delta media (as-is, o exportado)")
    ax.plot(raw["load_kw"], raw["delta_pct_media_corrected"],
            "D--", color="tab:orange",
            label=f"delta media corrigido (BL_sub / {median_ratio:.3f})")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Load_kW")
    ax.set_ylabel("delta_pct = (ADTV / BL − 1) · 100 [%]")
    ax.set_title("NOx — três comparações + correção de viés entre dias")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=9)
    p = out_dir / "delta_pct_tres_comparacoes.png"
    fig.tight_layout(); fig.savefig(p, dpi=140); plt.close(fig)

    # Plot 2: day-bias ratio per load
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(raw["load_kw"], raw["day_bias_ratio"], "o-", color="tab:red",
            label="BL_subida (Mar 06) / BL_descida (Mar 09)")
    ax.axhline(median_ratio, color="black", linestyle="--",
               label=f"mediana = {median_ratio:.3f}")
    ax.axhline(1.0, color="gray", linestyle=":", label="1,0 (sem viés)")
    ax.set_xlabel("Load_kW")
    ax.set_ylabel("razão NOx BL_sub / BL_des")
    ax.set_title("Assinatura do viés de dia — BL_subida (Mar 06) / BL_descida (Mar 09)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    p2 = out_dir / "day_bias_ratio_por_load.png"
    fig.tight_layout(); fig.savefig(p2, dpi=140); plt.close(fig)

    # Plot 3: ADTV_media vs BL_media, BL_media_corrigido (errorbars omitted — not the point)
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(raw["load_kw"], raw["BL_media_raw"],       "o-", color="tab:blue",
            label="BL_media (as-is — mistura Mar 06 + Mar 09)")
    ax.plot(raw["load_kw"], raw["BL_media_corrected"], "o--", color="tab:blue", alpha=0.5,
            label="BL_media corrigido (só referência Mar 09)")
    ax.plot(raw["load_kw"], raw["ADTV_media_raw"],     "s-", color="tab:red",
            label="ADTV_media (Mar 09 ambos lados)")
    ax.set_xlabel("Load_kW")
    ax.set_ylabel("NOx [ppm]")
    ax.set_title("NOx médio por campanha — evidencia o desnível do BL_media")
    ax.grid(True, alpha=0.3)
    ax.legend()
    p3 = out_dir / "nox_media_bl_adtv.png"
    fig.tight_layout(); fig.savefig(p3, dpi=140); plt.close(fig)

    print(f"\n[eval] plots: {p} , {p2} , {p3}")
    print(f"[eval] CSVs: nox_campaigns_and_deltas.csv, merged_report_vs_recomputed.csv")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
