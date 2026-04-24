"""Diagnose the BL vs ADTV NOx inversion between subida and descida.

Reads the 4 campaign folders from E:\\raw_pyton\\raw_NANUM, extracts raw NOx
mean per load, plus ambient/intake temperatures and the time column if
available. Then cross-checks against the values reported in
compare_iteracoes_metricas_incertezas.xlsx.

Outputs:
  - CSV with per-file raw means (nox, t_amb, t_adm, t_water, rpm, timestamp)
  - 3 PNGs:
      (1) raw NOx vs Load per campaign — shows the inversion
      (2) T_ambiente vs Load per campaign — between-day bias signature
      (3) raw mean vs report value scatter — confirms no processing error
  - A printed summary highlighting day-of-test per file group.
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


RAW_ROOT = Path(r"E:\raw_pyton\raw_NANUM")
CAMPAIGNS = {
    "BL_subida":   RAW_ROOT / "Subindo_baseline_2",
    "BL_descida":  RAW_ROOT / "Descendo_baseline_2",
    "ADTV_subida": RAW_ROOT / "subindo_aditivado_1",
    "ADTV_descida":RAW_ROOT / "descendo_aditivado_1",
}
COMPARE_XLSX = Path(r"E:\out_Nanum\plots\compare_iteracoes_bl_vs_adtv\compare_iteracoes_metricas_incertezas.xlsx")

NUMERIC_COL_CANDIDATES = {
    "nox":     ["NOX"],
    "t_amb":   ["T_AMBIENTE"],
    "t_adm":   ["T_ADMISSAO"],
    "t_water": ["T_S_AGUA", "T_E_AGUA"],
    "rpm":     ["RPM MOTOR"],
}


def _first_col(df, names):
    for n in names:
        for c in df.columns:
            if str(c).upper().replace(" ", "") == n.replace(" ", ""):
                return c
    return None


def _parse_load_from_name(name: str) -> float | None:
    import re
    m = re.search(r"(\d+(?:[,\.]\d+)?)\s*[kK][wW]", name)
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def inspect_file(p: Path) -> dict:
    try:
        df = pd.read_excel(p, engine="calamine")
    except Exception as e:
        return {"file": p.name, "error": str(e)}
    out = {"file": p.name, "n_rows": len(df)}
    for key, cands in NUMERIC_COL_CANDIDATES.items():
        col = _first_col(df, cands)
        if col is None:
            out[f"{key}_mean"] = None
            out[f"{key}_std"] = None
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        out[f"{key}_mean"] = float(s.mean()) if s.notna().any() else None
        out[f"{key}_std"]  = float(s.std())  if s.notna().any() else None
    # file mtime (OS) as proxy for acquisition day when internal clock isn't parsed
    out["mtime"] = datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="minutes")
    out["load_kw"] = _parse_load_from_name(p.name)
    return out


def collect() -> pd.DataFrame:
    rows = []
    for tag, folder in CAMPAIGNS.items():
        for xlsx in sorted(folder.glob("*.xlsx")):
            r = inspect_file(xlsx)
            r["campaign"] = tag
            rows.append(r)
    df = pd.DataFrame(rows)
    # split tag into bl/adtv and ramp
    df["run"] = df["campaign"].map(lambda t: "BL" if t.startswith("BL") else "ADTV")
    df["ramp"] = df["campaign"].map(lambda t: "subida" if "subida" in t else "descida")
    return df


def cross_check_with_report(raw: pd.DataFrame) -> pd.DataFrame:
    if not COMPARE_XLSX.exists():
        print(f"[WARN] compare xlsx not found: {COMPARE_XLSX}")
        return pd.DataFrame()
    rep = pd.read_excel(COMPARE_XLSX)
    rep = rep[rep["Metrica"].str.lower() == "nox"].copy()
    rep = rep[rep["Comparacao"].isin(["baseline_subida_vs_aditivado_subida",
                                      "baseline_descida_vs_aditivado_descida"])]
    pairs = []
    for _, row in rep.iterrows():
        load = row["Load_kW"]
        ramp = "subida" if "subida" in row["Comparacao"] else "descida"
        # BL raw at same load/ramp
        bl_raw = raw[(raw["run"] == "BL") & (raw["ramp"] == ramp) & (raw["load_kw"] == load)]
        adtv_raw = raw[(raw["run"] == "ADTV") & (raw["ramp"] == ramp) & (raw["load_kw"] == load)]
        if bl_raw.empty or adtv_raw.empty:
            continue
        pairs.append({
            "load_kw": load, "ramp": ramp,
            "bl_raw_mean":   float(bl_raw["nox_mean"].iloc[0])  if bl_raw["nox_mean"].iloc[0]   is not None else float("nan"),
            "bl_report":     float(row["value_left"]),
            "adtv_raw_mean": float(adtv_raw["nox_mean"].iloc[0]) if adtv_raw["nox_mean"].iloc[0] is not None else float("nan"),
            "adtv_report":   float(row["value_right"]),
        })
    cmp = pd.DataFrame(pairs)
    if cmp.empty:
        return cmp
    cmp["bl_diff_raw_minus_report"]   = cmp["bl_raw_mean"]   - cmp["bl_report"]
    cmp["adtv_diff_raw_minus_report"] = cmp["adtv_raw_mean"] - cmp["adtv_report"]
    cmp["bl_diff_rel_pct"]   = 100 * cmp["bl_diff_raw_minus_report"]   / cmp["bl_report"]
    cmp["adtv_diff_rel_pct"] = 100 * cmp["adtv_diff_raw_minus_report"] / cmp["adtv_report"]
    return cmp


def make_plots(raw: pd.DataFrame, cmp: pd.DataFrame, out_dir: Path) -> list[Path]:
    out: list[Path] = []
    markers = {("BL","subida"):"o", ("BL","descida"):"s",
               ("ADTV","subida"):"^", ("ADTV","descida"):"v"}
    colors  = {("BL","subida"):"tab:blue", ("BL","descida"):"tab:cyan",
               ("ADTV","subida"):"tab:red", ("ADTV","descida"):"tab:orange"}

    # Plot 1: NOx mean vs Load per campaign
    fig, ax = plt.subplots(figsize=(11, 6))
    for (run, ramp), g in raw.dropna(subset=["nox_mean","load_kw"]).groupby(["run","ramp"]):
        g = g.sort_values("load_kw")
        ax.plot(g["load_kw"], g["nox_mean"], marker=markers[(run,ramp)], color=colors[(run,ramp)],
                label=f"{run} {ramp}", linewidth=1.5, markersize=7)
    ax.set_xlabel("Load_kW")
    ax.set_ylabel("NOx médio (ppm, raw mean do arquivo LV)")
    ax.set_title("NOx raw por campanha — BL subida está em 2026-03-06, demais em 2026-03-09")
    ax.grid(True, alpha=0.3)
    ax.legend()
    p = out_dir / "nox_raw_por_campanha.png"
    fig.tight_layout(); fig.savefig(p, dpi=140); plt.close(fig)
    out.append(p)

    # Plot 2: T_ambiente vs Load per campaign (between-day bias signature)
    fig, ax = plt.subplots(figsize=(11, 6))
    for (run, ramp), g in raw.dropna(subset=["t_amb_mean","load_kw"]).groupby(["run","ramp"]):
        g = g.sort_values("load_kw")
        ax.plot(g["load_kw"], g["t_amb_mean"], marker=markers[(run,ramp)], color=colors[(run,ramp)],
                label=f"{run} {ramp}", linewidth=1.5, markersize=7)
    ax.set_xlabel("Load_kW")
    ax.set_ylabel("T_ambiente média [°C]")
    ax.set_title("T_ambiente por campanha — separa dia do ensaio")
    ax.grid(True, alpha=0.3)
    ax.legend()
    p = out_dir / "t_ambiente_por_campanha.png"
    fig.tight_layout(); fig.savefig(p, dpi=140); plt.close(fig)
    out.append(p)

    # Plot 3: raw mean vs report — confirms no processing bug
    if not cmp.empty:
        fig, ax = plt.subplots(figsize=(7, 7))
        ax.scatter(cmp["bl_report"],   cmp["bl_raw_mean"],   color="tab:blue",  label="BL",   s=40)
        ax.scatter(cmp["adtv_report"], cmp["adtv_raw_mean"], color="tab:red",   label="ADTV", s=40, marker="^")
        lo = min(cmp["bl_report"].min(), cmp["adtv_report"].min())
        hi = max(cmp["bl_report"].max(), cmp["adtv_report"].max())
        ax.plot([lo, hi], [lo, hi], "k--", alpha=0.5, label="y = x")
        ax.set_xlabel("NOx reportado (compare_iteracoes)")
        ax.set_ylabel("NOx raw mean (arquivo LV)")
        ax.set_title("Report vs raw — qualquer desvio apareceria fora da diagonal")
        ax.grid(True, alpha=0.3)
        ax.legend()
        p = out_dir / "nox_report_vs_raw.png"
        fig.tight_layout(); fig.savefig(p, dpi=140); plt.close(fig)
        out.append(p)
    return out


def main() -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="nox_inversion_"))
    print(f"[diag] out_dir: {out_dir}")
    raw = collect()
    raw.to_csv(out_dir / "raw_means_per_file.csv", index=False)
    print(f"[diag] raw files inspected: {len(raw)} | errors: {raw['n_rows'].isna().sum()}")

    # Day-of-test summary
    print("\n=== DIA DO ENSAIO (mtime do xlsx) por campanha ===")
    for tag, g in raw.groupby("campaign"):
        print(f"  {tag:15s}  mtime range: {g['mtime'].min()} .. {g['mtime'].max()}  N={len(g)}")

    # Inversion signature summary
    print("\n=== INVERSÃO — NOx mean por campanha × Load (amostra) ===")
    for load in [5.0, 20.0, 45.0]:
        sub = raw[raw["load_kw"] == load].set_index("campaign")
        if sub.empty:
            continue
        print(f"\n  Load = {load} kW:")
        for c in ["BL_subida","BL_descida","ADTV_subida","ADTV_descida"]:
            if c in sub.index:
                print(f"    {c:15s}  NOx={sub.loc[c,'nox_mean']:.1f}  T_amb={sub.loc[c,'t_amb_mean']:.1f}  T_adm_std={sub.loc[c,'t_adm_std']:.2f}")

    # Cross-check with report
    cmp = cross_check_with_report(raw)
    if not cmp.empty:
        cmp.to_csv(out_dir / "raw_vs_report.csv", index=False)
        print("\n=== RAW vs REPORT (NOx mean) — diferenças relativas ===")
        print(f"  BL   raw-report max rel [%]:  {cmp['bl_diff_rel_pct'].abs().max():.4f}")
        print(f"  BL   raw-report mean rel [%]: {cmp['bl_diff_rel_pct'].abs().mean():.4f}")
        print(f"  ADTV raw-report max rel [%]:  {cmp['adtv_diff_rel_pct'].abs().max():.4f}")
        print(f"  ADTV raw-report mean rel [%]: {cmp['adtv_diff_rel_pct'].abs().mean():.4f}")
        print("  (valores na ordem de 0.1% indicam que o pipeline lê fielmente o raw — a diferença é apenas do filtro de janelas.)")

    artifacts = make_plots(raw, cmp, out_dir)
    print("\n[diag] artefatos:")
    for a in artifacts:
        print(f"  {a}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
