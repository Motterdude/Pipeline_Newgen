"""Port nativo de summarize_time_diagnostics.

Reproduz nanum_pipeline_29.py::summarize_time_diagnostics (linhas 2285-2383).
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd

from .constants import (
    DEFAULT_MAX_ACT_CONTROL_ERROR_C,
    DEFAULT_MAX_DELTA_BETWEEN_SAMPLES_MS,
    DEFAULT_MAX_ECT_CONTROL_ERROR_C,
)
from .core import _to_float


def _time_diag_status_from_flags(flags: pd.Series) -> str:
    s = pd.Series(flags)
    valid = s.dropna()
    if valid.empty:
        return "NA"
    return "ERRO" if bool(valid.astype(bool).any()) else "OK"


def _first_last_transient_times(
    flags: pd.Series,
    time_parsed: pd.Series,
) -> Tuple[object, object]:
    mask = pd.Series(flags).fillna(False).astype(bool)
    if mask.sum() == 0:
        return pd.NA, pd.NA

    times = pd.to_datetime(pd.Series(time_parsed), errors="coerce")
    flagged_times = times[mask].dropna()
    if flagged_times.empty:
        return pd.NA, pd.NA

    return (
        flagged_times.iloc[0].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        flagged_times.iloc[-1].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
    )


def summarize_time_diagnostics(time_df: pd.DataFrame) -> pd.DataFrame:
    """Agregação por BaseName; uma linha por arquivo LV."""
    if time_df is None or time_df.empty:
        return pd.DataFrame()

    rows: List[dict] = []
    for basename, d in time_df.groupby("BaseName", dropna=False, sort=False):
        dt_next = pd.to_numeric(d["TIME_DELTA_TO_NEXT_s"], errors="coerce")
        err_ms = pd.to_numeric(d["TIME_DELTA_ERROR_ms"], errors="coerce")
        t_parsed = pd.to_datetime(d["TIME_PARSED"], errors="coerce")
        time_limit_ms = _to_float(
            d.get("MAX_DELTA_BETWEEN_SAMPLES_ms", pd.Series([DEFAULT_MAX_DELTA_BETWEEN_SAMPLES_MS])).iloc[0],
            DEFAULT_MAX_DELTA_BETWEEN_SAMPLES_MS,
        )
        time_limit_s = time_limit_ms / 1000.0
        time_flag = d.get("TIME_DELTA_ERROR_FLAG", pd.Series([pd.NA] * len(d)))
        smp_status = _time_diag_status_from_flags(time_flag)
        act_flag = d.get("ACT_CTRL_ERROR_FLAG", pd.Series([pd.NA] * len(d)))
        act_status = _time_diag_status_from_flags(act_flag)
        ect_flag = d.get("ECT_CTRL_ERROR_FLAG", pd.Series([pd.NA] * len(d)))
        ect_status = _time_diag_status_from_flags(ect_flag)
        dq_status = (
            "ERRO"
            if "ERRO" in {smp_status, act_status, ect_status}
            else ("OK" if {smp_status, act_status, ect_status} <= {"OK"} else "NA")
        )
        time_error_n = int(pd.Series(time_flag).fillna(False).astype(bool).sum()) if smp_status != "NA" else 0
        act_error_n = int(pd.Series(act_flag).fillna(False).astype(bool).sum()) if act_status != "NA" else 0
        ect_error_n = int(pd.Series(ect_flag).fillna(False).astype(bool).sum()) if ect_status != "NA" else 0
        act_abs = pd.to_numeric(d.get("ACT_CTRL_ERROR_ABS_C", pd.Series([pd.NA] * len(d))), errors="coerce")
        ect_abs = pd.to_numeric(d.get("ECT_CTRL_ERROR_ABS_C", pd.Series([pd.NA] * len(d))), errors="coerce")
        act_transient_status = act_status
        act_transient_t_on, act_transient_t_off = _first_last_transient_times(
            act_flag,
            d.get("TIME_PARSED", pd.Series([pd.NA] * len(d))),
        )
        ect_transient_status = ect_status
        ect_transient_t_on, ect_transient_t_off = _first_last_transient_times(
            ect_flag,
            d.get("TIME_PARSED", pd.Series([pd.NA] * len(d))),
        )
        max_act_error = _to_float(
            d.get("MAX_ACT_CONTROL_ERROR", pd.Series([DEFAULT_MAX_ACT_CONTROL_ERROR_C])).iloc[0],
            DEFAULT_MAX_ACT_CONTROL_ERROR_C,
        )
        max_ect_error = _to_float(
            d.get("MAX_ECT_CONTROL_ERROR", pd.Series([DEFAULT_MAX_ECT_CONTROL_ERROR_C])).iloc[0],
            DEFAULT_MAX_ECT_CONTROL_ERROR_C,
        )

        rows.append(
            {
                "Smp_ERROR": smp_status,
                "ACT_CTRL_ERRO": act_status,
                "ACT_CTRL_ERRO_TRANSIENTE": act_transient_status,
                "ACT_CTRL_ERRO_TRANSIENTE_t_on": act_transient_t_on,
                "ACT_CTRL_ERRO_TRANSIENTE_t_off": act_transient_t_off,
                "ECT_CTRL_ERRO": ect_status,
                "ECT_CTRL_ERRO_TRANSIENTE": ect_transient_status,
                "ECT_CTRL_ERRO_TRANSIENTE_t_on": ect_transient_t_on,
                "ECT_CTRL_ERRO_TRANSIENTE_t_off": ect_transient_t_off,
                "DQ_ERROR": dq_status,
                "BaseName": basename,
                "SourceFolder": d.get("SourceFolder", pd.Series([""])).iloc[0],
                "SourceFile": d.get("SourceFile", pd.Series([basename])).iloc[0],
                "Iteracao": pd.to_numeric(d.get("Iteracao", pd.Series([pd.NA])).iloc[0], errors="coerce"),
                "Sentido_Carga": d.get("Sentido_Carga", pd.Series([pd.NA])).iloc[0],
                "Load_kW": pd.to_numeric(d.get("Load_kW", pd.Series([pd.NA])).iloc[0], errors="coerce"),
                "DIES_pct": pd.to_numeric(d.get("DIES_pct", pd.Series([pd.NA])).iloc[0], errors="coerce"),
                "BIOD_pct": pd.to_numeric(d.get("BIOD_pct", pd.Series([pd.NA])).iloc[0], errors="coerce"),
                "EtOH_pct": pd.to_numeric(d.get("EtOH_pct", pd.Series([pd.NA])).iloc[0], errors="coerce"),
                "H2O_pct": pd.to_numeric(d.get("H2O_pct", pd.Series([pd.NA])).iloc[0], errors="coerce"),
                "N_samples": int(len(d)),
                "TIME_START": t_parsed.min(),
                "TIME_END": t_parsed.max(),
                "MAX_DELTA_BETWEEN_SAMPLES_ms": time_limit_ms,
                "TIME_DELTA_ERROR_N": time_error_n,
                "TIME_DELTA_ERROR_PCT": (time_error_n / len(d)) * 100.0 if len(d) > 0 else np.nan,
                "TIME_DELTA_MEDIAN_s": dt_next.median(),
                "TIME_DELTA_MEAN_s": dt_next.mean(),
                "TIME_DELTA_MIN_s": dt_next.min(),
                "TIME_DELTA_MAX_s": dt_next.max(),
                "TIME_DELTA_LIMIT_s": time_limit_s,
                "TIME_DELTA_STD_ms": dt_next.std(ddof=1) * 1000.0,
                "TIME_DELTA_MAX_ABS_ERROR_ms": err_ms.abs().max(),
                "TIME_DELTA_NONPOSITIVE_N": int((dt_next <= 0).fillna(False).sum()),
                "TIME_DELTA_MISSING_N": int(dt_next.isna().sum()),
                "MAX_ACT_CONTROL_ERROR": max_act_error,
                "ACT_CTRL_ERROR_N": act_error_n,
                "ACT_CTRL_ERROR_PCT": (act_error_n / len(d)) * 100.0 if len(d) > 0 else np.nan,
                "ACT_CTRL_ERROR_MEAN_ABS_C": act_abs.mean(),
                "ACT_CTRL_ERROR_MAX_ABS_C": act_abs.max(),
                "MAX_ECT_CONTROL_ERROR": max_ect_error,
                "ECT_CTRL_ERROR_N": ect_error_n,
                "ECT_CTRL_ERROR_PCT": (ect_error_n / len(d)) * 100.0 if len(d) > 0 else np.nan,
                "ECT_CTRL_ERROR_MEAN_ABS_C": ect_abs.mean(),
                "ECT_CTRL_ERROR_MAX_ABS_C": ect_abs.max(),
            }
        )

    out = pd.DataFrame(rows)
    if "Iteracao" in out.columns:
        out["Iteracao"] = pd.to_numeric(out["Iteracao"], errors="coerce").astype("Int64")
    return out
