"""Port nativo de plot_time_delta_by_file e plot_time_delta_all_samples.

Reproduz nanum_pipeline_29.py::plot_time_delta_all_samples (2386-2441) e
plot_time_delta_by_file (2443-2525).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .constants import (
    TIME_DELTA_ERROR_THRESHOLD_S,
    TIME_DELTA_PLOT_YMAX_S,
    TIME_DELTA_PLOT_YMIN_S,
    TIME_DELTA_PLOT_YSTEP_S,
    TIME_DIAG_FILE_SCATTER_MAX_POINTS,
    TIME_DIAG_PLOT_DPI,
)
from .core import _to_float


def _safe_name(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]+", "_", str(name))
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _time_diag_load_title(load_kw: object) -> str:
    v = pd.to_numeric(pd.Series([load_kw]), errors="coerce").iloc[0]
    if pd.isna(v):
        return "carga_desconhecida"
    v = float(v)
    txt = f"{int(v)}" if v.is_integer() else f"{v:g}".replace(".", ",")
    return f"{txt} kW"


def _time_diag_load_slug(load_kw: object) -> str:
    v = pd.to_numeric(pd.Series([load_kw]), errors="coerce").iloc[0]
    if pd.isna(v):
        return "carga_desconhecida"
    v = float(v)
    txt = f"{int(v)}" if v.is_integer() else f"{v:g}".replace(".", "p")
    return f"{txt}kW"


def _apply_time_delta_axis_format(ax) -> None:
    ax.set_ylim(TIME_DELTA_PLOT_YMIN_S, TIME_DELTA_PLOT_YMAX_S)
    ax.set_yticks(
        np.arange(
            TIME_DELTA_PLOT_YMIN_S,
            TIME_DELTA_PLOT_YMAX_S + (TIME_DELTA_PLOT_YSTEP_S * 0.5),
            TIME_DELTA_PLOT_YSTEP_S,
        )
    )


def plot_time_delta_all_samples(
    time_df: pd.DataFrame,
    filename: str = "time_delta_to_next_all_samples.png",
    plot_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Gera o PNG único com todos os samples concatenados (ordem global)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if time_df is None or time_df.empty:
        print("[WARN] Sem dados para plot de delta T do TIME.")
        return None

    d = time_df.sort_values(["BaseName", "Index"]).copy()
    x = pd.to_numeric(d["TIME_SAMPLE_GLOBAL"], errors="coerce")
    y = pd.to_numeric(d["TIME_DELTA_TO_NEXT_s"], errors="coerce")
    valid = x.notna() & y.notna()
    if valid.sum() == 0:
        print("[WARN] Sem delta T válido para plotar.")
        return None

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(x[valid], y[valid], "-", linewidth=0.8, color="tab:blue", alpha=0.85)
    valid_idx = np.flatnonzero(valid.to_numpy(dtype=bool))
    if len(valid_idx) > 0:
        step = max(len(valid_idx) // TIME_DIAG_FILE_SCATTER_MAX_POINTS, 1)
        scatter_idx = valid_idx[::step]
        ax.scatter(x.iloc[scatter_idx], y.iloc[scatter_idx], s=8, color="tab:blue", alpha=0.35)

    median_dt = float(y[valid].median())
    ax.axhline(median_dt, color="tab:red", linestyle="--", linewidth=1.0, label=f"median={median_dt:.6f} s")
    time_limit_s = _to_float(
        d.get("TIME_DELTA_LIMIT_s", pd.Series([TIME_DELTA_ERROR_THRESHOLD_S])).iloc[0],
        TIME_DELTA_ERROR_THRESHOLD_S,
    )
    ax.axhline(
        time_limit_s,
        color="tab:orange",
        linestyle=":",
        linewidth=1.2,
        label=f"limite erro={time_limit_s:.3f} s",
    )

    ax.set_xlabel("Global sample index")
    ax.set_ylabel("Delta T to next sample (s)")
    ax.set_title("TIME delta between consecutive samples")
    _apply_time_delta_axis_format(ax)
    ax.grid(True, which="both", linestyle="--", linewidth=0.5)
    ax.legend()

    target_dir = Path(".") if plot_dir is None else plot_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    outpath = target_dir / filename
    fig.tight_layout()
    fig.savefig(outpath, dpi=TIME_DIAG_PLOT_DPI)
    plt.close(fig)
    print(f"[OK] Salvei {outpath}")
    return outpath


def plot_time_delta_by_file(time_df: pd.DataFrame, plot_dir: Optional[Path] = None) -> int:
    """Gera um PNG por BaseName dentro de `<plot_dir>/time_delta_by_file/`. Retorna a contagem de PNGs escritos."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if time_df is None or time_df.empty:
        print("[WARN] Sem dados para plots individuais de delta T do TIME.")
        return 0

    base_dir = Path(".") if plot_dir is None else plot_dir
    out_dir = base_dir / "time_delta_by_file"
    out_dir.mkdir(parents=True, exist_ok=True)

    n_ok = 0
    n_skip = 0
    for basename, d in time_df.groupby("BaseName", dropna=False, sort=True):
        d = d.sort_values("Index").copy()
        x = pd.to_numeric(d["Index"], errors="coerce")
        y = pd.to_numeric(d["TIME_DELTA_TO_NEXT_s"], errors="coerce")
        valid = x.notna() & y.notna()
        if valid.sum() == 0:
            n_skip += 1
            continue

        source_folder = str(d.get("SourceFolder", pd.Series([""])).iloc[0] or "")
        source_file = str(d.get("SourceFile", pd.Series([basename])).iloc[0] or basename)
        load_kw = d.get("Load_kW", pd.Series([pd.NA])).iloc[0]
        load_title = _time_diag_load_title(load_kw)
        load_slug = _time_diag_load_slug(load_kw)
        time_limit_s = _to_float(
            d.get("TIME_DELTA_LIMIT_s", pd.Series([TIME_DELTA_ERROR_THRESHOLD_S])).iloc[0],
            TIME_DELTA_ERROR_THRESHOLD_S,
        )
        error_mask = valid & (y > time_limit_s)
        has_sampling_error = bool(error_mask.any())

        fig, ax = plt.subplots(figsize=(12, 4.5))
        ax.plot(x[valid], y[valid], "-", linewidth=0.9, color="tab:blue", alpha=0.9)
        valid_idx = np.flatnonzero(valid.to_numpy(dtype=bool))
        if len(valid_idx) > 0:
            step = max(len(valid_idx) // TIME_DIAG_FILE_SCATTER_MAX_POINTS, 1)
            scatter_idx = valid_idx[::step]
            ax.scatter(x.iloc[scatter_idx], y.iloc[scatter_idx], s=10, color="tab:blue", alpha=0.35)
        if has_sampling_error:
            ax.scatter(
                x[error_mask], y[error_mask],
                s=18, color="tab:red", alpha=0.95,
                label=f"delta T > {time_limit_s:.3f} s",
            )
            ax.set_facecolor("#fff4f4")
            for spine in ax.spines.values():
                spine.set_color("tab:red")
                spine.set_linewidth(1.2)

        median_dt = float(y[valid].median())
        ax.axhline(median_dt, color="tab:red", linestyle="--", linewidth=1.0, label=f"median={median_dt:.6f} s")
        ax.axhline(
            time_limit_s,
            color="tab:orange",
            linestyle=":",
            linewidth=1.2,
            label=f"limite erro={time_limit_s:.3f} s",
        )

        title_parts = ["TIME delta entre amostras", source_file]
        if has_sampling_error:
            title_parts.insert(0, "ERRO")
        if source_folder:
            title_parts.append(source_folder)
        title_parts.append(load_title)

        ax.set_xlabel("Sample index in file")
        ax.set_ylabel("Delta T to next sample (s)")
        ax.set_title(" | ".join(title_parts))
        _apply_time_delta_axis_format(ax)
        ax.grid(True, which="both", linestyle="--", linewidth=0.5)
        ax.legend()

        error_prefix = "ERRO_" if has_sampling_error else ""
        filename_stem = f"{error_prefix}time_delta_to_next_{source_folder}_{load_slug}_{source_file}"
        outpath = out_dir / f"{_safe_name(filename_stem)}.png"
        fig.tight_layout()
        fig.savefig(outpath, dpi=TIME_DIAG_PLOT_DPI)
        plt.close(fig)
        n_ok += 1

    print(f"[OK] Plots TIME por arquivo: {n_ok} gerados; {n_skip} pulados.")
    return n_ok
