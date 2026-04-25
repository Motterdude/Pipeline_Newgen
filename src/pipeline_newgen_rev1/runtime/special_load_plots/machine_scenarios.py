"""Machine-scenario plots: diesel vs ethanol comparisons across 3 machine types."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

from ..final_table.constants import MACHINE_SCENARIO_SPECS, SCENARIO_REFERENCE_FUEL_LABEL
from ..final_table._machine_scenarios import _scenario_machine_col
from ..final_table._fuel_defaults import _fuel_blend_labels
from ..final_table._helpers import resolve_col


def _resolve_x_col(df: pd.DataFrame) -> Tuple[Optional[str], str]:
    for candidate, label in [
        ("UPD_Power_Bin_kW", "Potencia UPD medida (kW, bin 0.1)"),
        ("UPD_Power_kW", "Potencia UPD medida (kW)"),
        ("Load_kW", "Carga nominal (kW)"),
    ]:
        try:
            col = resolve_col(df, candidate)
            return col, label
        except (KeyError, Exception):
            continue
    return None, ""


def _prepare_machine_scenario_plot_df(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, Optional[str], str]:
    if df is None or df.empty:
        return pd.DataFrame(), None, ""

    x_col, x_label = _resolve_x_col(df)
    if x_col is None:
        return pd.DataFrame(), None, ""

    fuel_labels = df.get("Fuel_Label", pd.Series(pd.NA, index=df.index, dtype="object"))
    fuel_labels = fuel_labels.where(fuel_labels.notna(), _fuel_blend_labels(df))
    out = df[fuel_labels.eq(SCENARIO_REFERENCE_FUEL_LABEL)].copy()
    if out.empty:
        return pd.DataFrame(), x_col, x_label

    out[x_col] = pd.to_numeric(out[x_col], errors="coerce")
    out = out.dropna(subset=[x_col]).sort_values(x_col)
    return out, x_col, x_label


def _machine_scaled_tick_formatter(divisor: float):
    from matplotlib.ticker import FuncFormatter
    return FuncFormatter(lambda value, _pos: f"{(value / divisor):g}")


def _reserve_upper_legend_headroom(ax, *, ratio: float = 0.32) -> None:
    import numpy as np
    try:
        ymin, ymax = ax.get_ylim()
    except Exception:
        return
    if not (np.isfinite(ymin) and np.isfinite(ymax)):
        return
    span = ymax - ymin
    if not np.isfinite(span) or span <= 0:
        span = max(abs(ymax), abs(ymin), 1.0)
    ax.set_ylim(ymin, ymax + span * ratio)


def _style_machine_scenario_axes(
    fig,
    ax,
    *,
    title: str,
    x_label: str,
    y_label: str,
    y_tick_divisor: Optional[float] = None,
) -> None:
    import numpy as np
    ax.set_xlim(0.0, 55.0)
    ax.set_xticks(list(np.arange(0.0, 55.0 + 1e-12, 5.0)))
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.grid(True, which="both", linestyle="--", linewidth=0.5)
    if (
        y_tick_divisor is not None
        and float(y_tick_divisor) > 0
        and float(y_tick_divisor) != 1.0
    ):
        ax.yaxis.set_major_formatter(_machine_scaled_tick_formatter(float(y_tick_divisor)))

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        _reserve_upper_legend_headroom(ax)
        ax.legend(loc="upper left", frameon=True)
    fig.tight_layout()


def _plot_machine_scenario_dual_metric(
    df: pd.DataFrame,
    *,
    diesel_suffix: str,
    ethanol_suffix: str,
    ethanol_u_suffix: Optional[str],
    title: str,
    filename: str,
    y_label: str,
    plot_dir: Path,
    y_tick_divisor: Optional[float] = None,
) -> Optional[Path]:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    plot_df, x_col, x_label = _prepare_machine_scenario_plot_df(df)
    if x_col is None or plot_df.empty:
        print(f"[WARN] machine_scenario_dual | no {SCENARIO_REFERENCE_FUEL_LABEL} data for {filename}.")
        return None

    fig, ax = plt.subplots()
    any_curve = False
    for spec in MACHINE_SCENARIO_SPECS:
        diesel_col = _scenario_machine_col(spec["key"], diesel_suffix)
        ethanol_col = _scenario_machine_col(spec["key"], ethanol_suffix)
        ethanol_u_col = _scenario_machine_col(spec["key"], ethanol_u_suffix) if ethanol_u_suffix else None

        if diesel_col in plot_df.columns:
            d_diesel = plot_df[[x_col, diesel_col]].copy()
            d_diesel[diesel_col] = pd.to_numeric(d_diesel[diesel_col], errors="coerce")
            d_diesel = d_diesel.dropna(subset=[x_col, diesel_col]).sort_values(x_col)
            if not d_diesel.empty:
                any_curve = True
                ax.plot(
                    d_diesel[x_col], d_diesel[diesel_col], "o--",
                    color=spec["color"], linewidth=1.8, markersize=4.5,
                    label=f"{spec['label']} diesel",
                )

        if ethanol_col in plot_df.columns:
            cols = [x_col, ethanol_col]
            if ethanol_u_col and ethanol_u_col in plot_df.columns:
                cols.append(ethanol_u_col)
            d_eth = plot_df[cols].copy()
            d_eth[ethanol_col] = pd.to_numeric(d_eth[ethanol_col], errors="coerce")
            if ethanol_u_col and ethanol_u_col in d_eth.columns:
                d_eth[ethanol_u_col] = pd.to_numeric(d_eth[ethanol_u_col], errors="coerce")
            d_eth = d_eth.dropna(subset=[x_col, ethanol_col]).sort_values(x_col)
            if d_eth.empty:
                continue

            any_curve = True
            if ethanol_u_col and ethanol_u_col in d_eth.columns and d_eth[ethanol_u_col].notna().any():
                ax.errorbar(
                    d_eth[x_col], d_eth[ethanol_col], yerr=d_eth[ethanol_u_col],
                    fmt="o-", capsize=3, color=spec["color"], linewidth=1.8, markersize=4.5,
                    label=f"{spec['label']} {SCENARIO_REFERENCE_FUEL_LABEL}",
                )
            else:
                ax.plot(
                    d_eth[x_col], d_eth[ethanol_col], "o-",
                    color=spec["color"], linewidth=1.8, markersize=4.5,
                    label=f"{spec['label']} {SCENARIO_REFERENCE_FUEL_LABEL}",
                )

    if not any_curve:
        plt.close(fig)
        return None

    _style_machine_scenario_axes(fig, ax, title=title, x_label=x_label, y_label=y_label, y_tick_divisor=y_tick_divisor)
    outpath = plot_dir / filename
    fig.savefig(outpath, dpi=200)
    plt.close(fig)
    return outpath


def _plot_machine_scenario_single_metric(
    df: pd.DataFrame,
    *,
    value_suffix: str,
    u_suffix: Optional[str],
    title: str,
    filename: str,
    y_label: str,
    plot_dir: Path,
    y_tick_divisor: Optional[float] = None,
) -> Optional[Path]:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    plot_df, x_col, x_label = _prepare_machine_scenario_plot_df(df)
    if x_col is None or plot_df.empty:
        print(f"[WARN] machine_scenario_single | no {SCENARIO_REFERENCE_FUEL_LABEL} data for {filename}.")
        return None

    fig, ax = plt.subplots()
    any_curve = False
    for spec in MACHINE_SCENARIO_SPECS:
        value_col = _scenario_machine_col(spec["key"], value_suffix)
        u_col = _scenario_machine_col(spec["key"], u_suffix) if u_suffix else None
        if value_col not in plot_df.columns:
            continue

        cols = [x_col, value_col]
        if u_col and u_col in plot_df.columns:
            cols.append(u_col)

        d = plot_df[cols].copy()
        d[value_col] = pd.to_numeric(d[value_col], errors="coerce")
        if u_col and u_col in d.columns:
            d[u_col] = pd.to_numeric(d[u_col], errors="coerce")
        d = d.dropna(subset=[x_col, value_col]).sort_values(x_col)
        if d.empty:
            continue

        any_curve = True
        if u_col and u_col in d.columns and d[u_col].notna().any():
            ax.errorbar(
                d[x_col], d[value_col], yerr=d[u_col],
                fmt="o-", capsize=3, color=spec["color"], linewidth=1.8, markersize=4.5,
                label=spec["label"],
            )
        else:
            ax.plot(
                d[x_col], d[value_col], "o-",
                color=spec["color"], linewidth=1.8, markersize=4.5,
                label=spec["label"],
            )

    if not any_curve:
        plt.close(fig)
        return None

    _style_machine_scenario_axes(fig, ax, title=title, x_label=x_label, y_label=y_label, y_tick_divisor=y_tick_divisor)
    outpath = plot_dir / filename
    fig.savefig(outpath, dpi=200)
    plt.close(fig)
    return outpath


def plot_machine_scenario_suite(df: pd.DataFrame, *, plot_dir: Path) -> int:
    count = 0
    calls = [
        lambda: _plot_machine_scenario_dual_metric(
            df, diesel_suffix="Diesel_Custo_R_h", ethanol_suffix="E94H6_Custo_R_h",
            ethanol_u_suffix="U_E94H6_Custo_R_h",
            title="Cenario de maquinas: custo horario diesel vs E94H6",
            filename="scenario_maquinas_custo_r_h_diesel_vs_e94h6.png",
            y_label="Custo horario (R$/h)", plot_dir=plot_dir,
        ),
        lambda: _plot_machine_scenario_single_metric(
            df, value_suffix="Economia_R_h", u_suffix="U_Economia_R_h",
            title="Cenario de maquinas: economia horaria vs diesel (negativo = economia)",
            filename="scenario_maquinas_economia_r_h_vs_diesel.png",
            y_label="Delta de custo vs diesel (R$/h)", plot_dir=plot_dir,
        ),
        lambda: _plot_machine_scenario_dual_metric(
            df, diesel_suffix="Diesel_L_h", ethanol_suffix="E94H6_L_h",
            ethanol_u_suffix="U_E94H6_L_h",
            title="Cenario de maquinas: consumo volumetrico diesel vs E94H6",
            filename="scenario_maquinas_consumo_l_h_diesel_vs_e94h6.png",
            y_label="Consumo volumetrico (L/h)", plot_dir=plot_dir,
        ),
        lambda: _plot_machine_scenario_single_metric(
            df, value_suffix="E94H6_L_ano", u_suffix="U_E94H6_L_ano",
            title="Cenario de maquinas: consumo anual de E94H6",
            filename="scenario_maquinas_consumo_anual_e94h6_l.png",
            y_label="Consumo anual de E94H6 (x10^3 L/ano)",
            plot_dir=plot_dir, y_tick_divisor=1000.0,
        ),
        lambda: _plot_machine_scenario_dual_metric(
            df, diesel_suffix="Diesel_Custo_R_ano", ethanol_suffix="E94H6_Custo_R_ano",
            ethanol_u_suffix="U_E94H6_Custo_R_ano",
            title="Cenario de maquinas: custo anual diesel vs E94H6",
            filename="scenario_maquinas_custo_anual_diesel_vs_e94h6.png",
            y_label="Custo anual (x10^3 R$/ano)",
            plot_dir=plot_dir, y_tick_divisor=1000.0,
        ),
        lambda: _plot_machine_scenario_single_metric(
            df, value_suffix="Economia_R_ano", u_suffix="U_Economia_R_ano",
            title="Cenario de maquinas: economia anual vs diesel (negativo = economia)",
            filename="scenario_maquinas_economia_anual_vs_diesel.png",
            y_label="Delta de custo anual vs diesel (x10^3 R$/ano)",
            plot_dir=plot_dir, y_tick_divisor=1000.0,
        ),
    ]
    for call in calls:
        result = call()
        if result is not None:
            count += 1
    return count
