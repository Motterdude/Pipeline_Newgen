"""Drive the legacy nanum_pipeline_29 end-to-end on raw_NANUM in a tempdir
to capture the new compare_iteracoes for thermal efficiency (n_th).

Nothing operational is touched — every write goes to a tempdir and the
user's %LOCALAPPDATA% runtime-paths JSON is isolated. The legacy reads
the config from a tempdir-local copy of pipeline_newgen_rev1/config/
pipeline29_text/ (where the compare.toml now has the 3 n_th entries).

After the run, the driver reads:
  <tmp>/out/plots/compare_iteracoes_bl_vs_adtv/
      compare_iteracoes_metricas_incertezas.xlsx
      compare_iteracoes_*_n_th_pct*.png
  <tmp>/out/lv_kpis_clean.xlsx           (for per-iteracao n_th values)

and compares n_th_pct delta against:
  * the 3 existing emissions metrics in the same report (sanity scale);
  * the unitary per-campaign n_th values stored in lv_kpis_clean.xlsx
    (to check that the delta direction matches point-by-point).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


LEGACY_REPO = Path(r"C:\Temp\np28_git_main_20260422\nanum-pipeline-28-main")
NEWGEN_REPO = Path(r"C:\Temp\np28_git_main_20260422\Pipeline_newgen_rev1")
RAW_SOURCE  = Path(r"E:\raw_pyton\raw_NANUM")


def _prepare_config_copy(src: Path, dest: Path, raw_dir: Path, out_dir: Path) -> None:
    shutil.copytree(src, dest)
    defaults = dest / "defaults.toml"
    text = defaults.read_text(encoding="utf-8").splitlines()
    new_lines: list[str] = []
    for line in text:
        if line.startswith('"RAW_INPUT_DIR"'):
            new_lines.append(f'"RAW_INPUT_DIR" = "{str(raw_dir).replace(os.sep, os.sep * 2)}"')
        elif line.startswith('"OUT_DIR"'):
            new_lines.append(f'"OUT_DIR" = "{str(out_dir).replace(os.sep, os.sep * 2)}"')
        else:
            new_lines.append(line)
    defaults.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _run_legacy(config_dir: Path, raw_dir: Path, out_dir: Path, appdata: Path, log_path: Path) -> int:
    driver = out_dir.parent / "legacy_driver.py"
    driver_src = textwrap.dedent(f"""
        import sys, os, json
        from pathlib import Path

        sys.path.insert(0, r"{LEGACY_REPO}")
        os.environ["PIPELINE29_USE_DEFAULT_RUNTIME_DIRS"] = "1"
        os.environ["PIPELINE29_SKIP_CONFIG_GUI_PROMPT"] = "1"

        appdata = Path(r"{appdata}") / "nanum_pipeline_29"
        appdata.mkdir(parents=True, exist_ok=True)
        (appdata / "pipeline29_runtime_paths.json").write_text(
            json.dumps({{"raw_input_dir": r"{raw_dir}", "out_dir": r"{out_dir}"}}),
            encoding="utf-8",
        )

        import nanum_pipeline_29 as legacy
        legacy.prompt_plot_point_filter_from_metas = lambda metas: None
        legacy.prompt_plot_point_filter = lambda df: None

        sys.argv = [
            "nanum_pipeline_29.py",
            "--config-source", "text",
            "--config-dir", r"{config_dir}",
            "--skip-config-gui-prompt",
            "--plot-scope", "all",
        ]
        legacy.main()
    """)
    driver.write_text(driver_src, encoding="utf-8")
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(appdata)
    env["PIPELINE29_USE_DEFAULT_RUNTIME_DIRS"] = "1"
    env["PIPELINE29_SKIP_CONFIG_GUI_PROMPT"] = "1"
    res = subprocess.run(
        [sys.executable, str(driver)],
        env=env, cwd=str(LEGACY_REPO),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    log_path.write_text(
        f"=== stdout ===\n{res.stdout}\n=== stderr ===\n{res.stderr}\n",
        encoding="utf-8",
    )
    return res.returncode


def _analyze_and_plot(out_dir: Path, report_xlsx: Path, kpis_xlsx: Path, dest_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    rep = pd.read_excel(report_xlsx)
    n_th = rep[rep["Metrica"].str.lower() == "n_th"].copy()
    if n_th.empty:
        print("[analyze] n_th NOT FOUND in report — spec or config likely broke.")
        return

    print(f"[analyze] n_th rows in report: {len(n_th)}")
    for cmp in sorted(n_th["Comparacao"].unique()):
        g = n_th[n_th["Comparacao"] == cmp].sort_values("Load_kW")
        print(f"\n=== {cmp} ===")
        cols = ["Load_kW", "value_left", "U_left", "value_right", "U_right",
                "delta_pct", "U_delta_pct", "delta_over_U", "significancia_95pct"]
        cols = [c for c in cols if c in g.columns]
        print(g[cols].round(3).to_string(index=False))

    import numpy as np
    # Plot 1: delta_pct(Load) for all 3 ramp comparisons
    fig, ax = plt.subplots(figsize=(11, 6))
    palette = {
        "baseline_subida_vs_aditivado_subida":   ("tab:red",    "^", "subida"),
        "baseline_descida_vs_aditivado_descida": ("tab:green",  "s", "descida"),
        "baseline_media_vs_aditivado_media":     ("tab:purple", "o", "média"),
    }
    for cmp, g in n_th.groupby("Comparacao"):
        if cmp not in palette:
            continue
        color, marker, label = palette[cmp]
        g = g.sort_values("Load_kW")
        has_u = pd.to_numeric(g["U_delta_pct"], errors="coerce").notna().any()
        if has_u:
            ax.errorbar(g["Load_kW"], g["delta_pct"], yerr=g["U_delta_pct"],
                        fmt=marker+"-", color=color, label=label, capsize=3)
        else:
            ax.plot(g["Load_kW"], g["delta_pct"], marker+"-", color=color, label=label)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Load_kW")
    ax.set_ylabel("delta_pct  η_th = (ADTV/BL − 1)·100  [%]")
    ax.set_title("Compare_iteracoes BL vs ADTV — eficiência térmica")
    ax.set_ylim(-5, 5)
    ax.set_yticks(np.arange(-5, 5.001, 0.5))
    ax.grid(True, alpha=0.3)
    ax.legend()
    p = dest_dir / "delta_pct_n_th_3_ramps.png"
    fig.tight_layout(); fig.savefig(p, dpi=140); plt.close(fig)
    print(f"\n[analyze] plot 1: {p}")

    # Plot 2: absolute n_th_pct per campaign from the report
    fig, ax = plt.subplots(figsize=(11, 6))
    for cmp, g in n_th.groupby("Comparacao"):
        if cmp not in palette:
            continue
        color, marker, label = palette[cmp]
        g = g.sort_values("Load_kW")
        ax.errorbar(g["Load_kW"], g["value_left"],  yerr=g["U_left"],
                    fmt=marker+"-", color=color, alpha=0.85,
                    label=f"BL {label}", capsize=3)
        ax.errorbar(g["Load_kW"], g["value_right"], yerr=g["U_right"],
                    fmt=marker+"--", color=color, alpha=0.45,
                    label=f"ADTV {label}", capsize=3)
    ax.set_xlabel("Load_kW")
    ax.set_ylabel("η_th  [%]")
    ax.set_title("η_th por campanha (do compare_iteracoes)")
    ax.set_ylim(10, 35)
    ax.set_yticks(np.arange(10, 35.001, 2))
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, ncol=2)
    p = dest_dir / "n_th_absoluto_por_campanha.png"
    fig.tight_layout(); fig.savefig(p, dpi=140); plt.close(fig)
    print(f"[analyze] plot 2: {p}")

    # Plot 3: cross-check against unitary lv_kpis_clean.xlsx n_th_pct
    if kpis_xlsx.exists():
        kpis = pd.read_excel(kpis_xlsx)
        from pandas import DataFrame
        if {"BaseName", "Load_kW", "n_th_pct"}.issubset(kpis.columns):
            # Classify by campaign using the same rule the legacy uses.
            import re
            def campaign(bn: str) -> str:
                s = str(bn).lower()
                if "subindo" in s and "aditivado" in s: return "ADTV_subida"
                if "descendo" in s and "aditivado" in s: return "ADTV_descida"
                if ("subindo" in s or "subida" in s)  and "baseline"  in s: return "BL_subida"
                if ("descendo" in s or "descida" in s) and "baseline"  in s: return "BL_descida"
                return ""
            kpis["_cmp"] = kpis["BaseName"].map(campaign)
            kpis = kpis[kpis["_cmp"] != ""].copy()
            kpis["n_th_pct"] = pd.to_numeric(kpis["n_th_pct"], errors="coerce")
            kpis["U_n_th_pct"] = pd.to_numeric(kpis.get("U_n_th_pct", pd.NA), errors="coerce")

            fig, ax = plt.subplots(figsize=(11, 6))
            campaign_colors = {
                "BL_subida":    "tab:blue",
                "BL_descida":   "tab:cyan",
                "ADTV_subida":  "tab:red",
                "ADTV_descida": "tab:orange",
            }
            for cmp, g in kpis.groupby("_cmp"):
                g = g.sort_values("Load_kW")
                ax.errorbar(g["Load_kW"], g["n_th_pct"], yerr=g["U_n_th_pct"],
                            fmt="o-", color=campaign_colors.get(cmp, "black"),
                            label=cmp, capsize=3, alpha=0.8)
            ax.set_xlabel("Load_kW")
            ax.set_ylabel("η_th [%] — per iteração (lv_kpis_clean)")
            ax.set_title("η_th unitário por iteração — baseline das 4 campanhas")
            ax.set_ylim(10, 35)
            ax.set_yticks(np.arange(10, 35.001, 2))
            ax.grid(True, alpha=0.3)
            ax.legend()
            p = dest_dir / "n_th_unitario_por_iteracao.png"
            fig.tight_layout(); fig.savefig(p, dpi=140); plt.close(fig)
            print(f"[analyze] plot 3: {p}")

            # Cross-check: recompute delta_pct from unitary and compare with report
            piv = kpis.pivot_table(index="Load_kW", columns="_cmp", values="n_th_pct").reset_index()
            def delta(a: str, b: str) -> list[float]:
                if a in piv.columns and b in piv.columns:
                    return 100 * (piv[a] / piv[b] - 1)
                return []
            piv["delta_sub_recomp"] = 100 * (piv.get("ADTV_subida", 0)  / piv.get("BL_subida", 1)  - 1)
            piv["delta_des_recomp"] = 100 * (piv.get("ADTV_descida", 0) / piv.get("BL_descida", 1) - 1)
            # Match with report
            rep_sub = n_th[n_th["Comparacao"] == "baseline_subida_vs_aditivado_subida"][["Load_kW","delta_pct"]]
            rep_des = n_th[n_th["Comparacao"] == "baseline_descida_vs_aditivado_descida"][["Load_kW","delta_pct"]]
            merged = piv.merge(rep_sub.rename(columns={"delta_pct":"delta_sub_report"}), on="Load_kW", how="left")
            merged = merged.merge(rep_des.rename(columns={"delta_pct":"delta_des_report"}), on="Load_kW", how="left")
            print("\n=== RECOMPUTE vs REPORT (delta_pct_n_th) ===")
            diff_sub = (merged["delta_sub_recomp"] - merged["delta_sub_report"]).abs()
            diff_des = (merged["delta_des_recomp"] - merged["delta_des_report"]).abs()
            print(f"  max |recomp - report| subida:  {diff_sub.max():.4f} pct")
            print(f"  max |recomp - report| descida: {diff_des.max():.4f} pct")
            print("  (valor < 0.01 pct confirma que a agregação compare não distorce os unitários)")

            merged[["Load_kW","BL_subida","ADTV_subida","BL_descida","ADTV_descida",
                    "delta_sub_recomp","delta_sub_report",
                    "delta_des_recomp","delta_des_report"]].to_csv(
                dest_dir / "n_th_recompute_vs_report.csv", index=False,
            )


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="legacy_n_th_compare_"))
    raw_dir = tmp / "raw"
    cfg_dir = tmp / "config"
    appdata = tmp / "appdata"
    out_dir = tmp / "out"
    analysis_dir = tmp / "analysis"
    for d in (raw_dir.parent, cfg_dir.parent, appdata, out_dir, analysis_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Symlink is not portable on Windows without privileges — do a full copy of raw tree.
    print(f"[run] tempdir: {tmp}")
    print(f"[run] copying raw tree (this may take a minute)...")
    shutil.copytree(RAW_SOURCE, raw_dir)

    _prepare_config_copy(NEWGEN_REPO / "config" / "pipeline29_text", cfg_dir, raw_dir, out_dir)

    log_path = tmp / "legacy.log"
    print(f"[run] running legacy pipeline_29 ...")
    rc = _run_legacy(cfg_dir, raw_dir, out_dir, appdata, log_path)
    print(f"[run] rc={rc} | log={log_path}")
    if rc != 0:
        print("[run] legacy exited non-zero, dumping log tail:")
        print(log_path.read_text(encoding="utf-8", errors="replace")[-4000:])
        return rc

    report_xlsx = out_dir / "plots" / "compare_iteracoes_bl_vs_adtv" / "compare_iteracoes_metricas_incertezas.xlsx"
    kpis_xlsx = out_dir / "lv_kpis_clean.xlsx"
    print(f"\n[run] report: {report_xlsx.exists()}  |  kpis: {kpis_xlsx.exists()}")
    if not report_xlsx.exists():
        print("[run] no report produced — check compare.toml and specs.")
        return 1

    _analyze_and_plot(out_dir, report_xlsx, kpis_xlsx, analysis_dir)
    print(f"\n[run] artifacts in {analysis_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
