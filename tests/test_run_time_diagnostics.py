"""Unit tests for the native RunTimeDiagnosticsStage + the time_diagnostics subpackage."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import unittest

from pipeline_newgen_rev1.runtime.context import RuntimeContext
from pipeline_newgen_rev1.runtime.stages.run_time_diagnostics import RunTimeDiagnosticsStage
from pipeline_newgen_rev1.runtime.time_diagnostics import (
    build_time_diagnostics,
    plot_time_delta_by_file,
    summarize_time_diagnostics,
)


def _synthetic_lv_frame(basename: str, n_samples: int = 100, load_kw: float = 20.0) -> pd.DataFrame:
    base_time = pd.Timestamp("2026-03-09 12:00:00")
    times = [base_time + pd.Timedelta(seconds=i) for i in range(n_samples)]
    return pd.DataFrame(
        {
            "BaseName": [basename] * n_samples,
            "Load_kW": [load_kw] * n_samples,
            "DIES_pct": [85.0] * n_samples,
            "BIOD_pct": [15.0] * n_samples,
            "EtOH_pct": [0.0] * n_samples,
            "H2O_pct": [0.0] * n_samples,
            "Index": list(range(n_samples)),
            "Time": times,
            "T_ADMISSAO": np.full(n_samples, 60.0),
            "DEM ACT AQUECEDOR": np.full(n_samples, 60.0),
            "T_S_AGUA": np.full(n_samples, 85.0),
            "DEM_TH2O": np.full(n_samples, 85.0),
        }
    )


class BuildTimeDiagnosticsColumnsTest(unittest.TestCase):
    def test_builds_expected_columns(self):
        lv_raw = _synthetic_lv_frame("Subindo_baseline_1__D85B15_20kW")
        time_df = build_time_diagnostics(lv_raw, quality_cfg={"MAX_DELTA_BETWEEN_SAMPLES_ms": 1200.0})
        expected = {
            "BaseName", "Load_kW", "TIME_PARSED", "TIME_HOUR", "TIME_MINUTE",
            "TIME_SECOND", "TIME_MILLISECOND", "TIME_DELTA_FROM_PREV_s",
            "TIME_DELTA_TO_NEXT_s", "TIME_DELTA_TO_NEXT_ms",
            "TIME_DELTA_REFERENCE_s", "TIME_DELTA_ERROR_ms",
            "MAX_DELTA_BETWEEN_SAMPLES_ms", "TIME_DELTA_LIMIT_s",
            "TIME_DELTA_LIMIT_ms", "TIME_DELTA_ERROR_FLAG", "TIME_SAMPLE_GLOBAL",
            "ACT_CTRL_ACTUAL_C", "ACT_CTRL_TARGET_C", "ACT_CTRL_ERROR_C",
            "ACT_CTRL_ERROR_ABS_C", "ACT_CTRL_ERROR_FLAG",
            "ECT_CTRL_ACTUAL_C", "ECT_CTRL_TARGET_C", "ECT_CTRL_ERROR_C",
            "ECT_CTRL_ERROR_ABS_C", "ECT_CTRL_ERROR_FLAG",
            "SourceFolder", "SourceFile", "Sentido_Carga", "Iteracao",
        }
        missing = expected - set(time_df.columns)
        self.assertFalse(missing, f"missing columns: {missing}")

    def test_empty_input_returns_empty(self):
        self.assertTrue(build_time_diagnostics(pd.DataFrame()).empty)

    def test_missing_time_column_returns_empty(self):
        df = pd.DataFrame({"BaseName": ["x"], "Load_kW": [10.0]})
        self.assertTrue(build_time_diagnostics(df).empty)


class SummarizeTimeDiagnosticsTest(unittest.TestCase):
    def test_summary_rollup_one_row_per_basename(self):
        frames = [
            _synthetic_lv_frame("Subindo_baseline_1__D85B15_20kW", n_samples=60),
            _synthetic_lv_frame("Subindo_baseline_1__D85B15_25kW", n_samples=80),
            _synthetic_lv_frame("Descendo_baseline_1__D85B15_20kW", n_samples=50),
        ]
        lv_raw = pd.concat(frames, ignore_index=True)
        time_df = build_time_diagnostics(lv_raw)
        summary = summarize_time_diagnostics(time_df)
        self.assertEqual(len(summary), 3)
        self.assertEqual(sorted(summary["N_samples"].tolist()), [50, 60, 80])


class PlotTimeDeltaByFileTest(unittest.TestCase):
    def test_plots_per_file_produces_n_pngs(self):
        frames = [_synthetic_lv_frame(f"Subindo_baseline_1__D85B15_{n}kW", n_samples=40) for n in (5, 10, 15)]
        lv_raw = pd.concat(frames, ignore_index=True)
        time_df = build_time_diagnostics(lv_raw)
        with tempfile.TemporaryDirectory() as tmp:
            count = plot_time_delta_by_file(time_df, plot_dir=Path(tmp))
            self.assertEqual(count, 3)
            pngs = list((Path(tmp) / "time_delta_by_file").glob("*.png"))
            self.assertEqual(len(pngs), 3)


class StageSkipsWhenEmptyTest(unittest.TestCase):
    def test_skips_when_labview_frames_empty(self):
        ctx = RuntimeContext(project_root=Path("."))
        ctx.labview_frames = []  # empty
        ctx.output_dir = None
        stage = RunTimeDiagnosticsStage()
        stage.run(ctx)  # should not raise
        self.assertIsNone(ctx.time_diagnostics)


class StageRespectsDataQualityCfgTest(unittest.TestCase):
    def test_tighter_max_delta_flags_more_samples(self):
        # With 1-second sampling, MAX_DELTA=500ms flags every sample as error.
        lv_raw = _synthetic_lv_frame("Subindo_baseline_1__D85B15_20kW", n_samples=30)
        strict = build_time_diagnostics(lv_raw, quality_cfg={"MAX_DELTA_BETWEEN_SAMPLES_ms": 500.0})
        loose = build_time_diagnostics(lv_raw, quality_cfg={"MAX_DELTA_BETWEEN_SAMPLES_ms": 1200.0})
        n_strict = pd.Series(strict["TIME_DELTA_ERROR_FLAG"]).fillna(False).astype(bool).sum()
        n_loose = pd.Series(loose["TIME_DELTA_ERROR_FLAG"]).fillna(False).astype(bool).sum()
        self.assertGreater(n_strict, n_loose)


if __name__ == "__main__":
    unittest.main()
