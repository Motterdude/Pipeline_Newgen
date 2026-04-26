"""Unit tests for ``RunUnitaryPlotsBridgeStage`` using a mocked legacy module."""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.runtime.context import RuntimeContext


class _StubBundle:
    def __init__(self) -> None:
        self.plots_df = pd.DataFrame({"y_col": ["BSFC_g_kWh"], "x_col": ["Load_kW"]})
        self.mappings = {"power_kw": {"mean": "Power_kW"}}


def _install_stub_legacy(*, raise_in_plot: bool = False) -> MagicMock:
    module = types.ModuleType("nanum_pipeline_29")
    tracker = MagicMock()

    def _load_pipeline29_config_bundle(**_kwargs):
        tracker.load_pipeline29_config_bundle(**_kwargs)
        return _StubBundle()

    def _make_plots_from_config_with_summary(out_df, plots_df, mappings, plot_dir=None, series_col=None):
        tracker.make_plots_from_config_with_summary(
            out_df_rows=len(out_df), plots_df_rows=len(plots_df), plot_dir=str(plot_dir)
        )
        if raise_in_plot:
            raise RuntimeError("synthetic plot failure")
        return {
            "generated": 1,
            "generated_labels": ["BSFC_vs_Load"],
            "generated_files": [str(plot_dir / "BSFC_vs_Load.png")],
            "skipped": 0,
            "disabled": 0,
        }

    module.load_pipeline29_config_bundle = _load_pipeline29_config_bundle
    module.make_plots_from_config_with_summary = _make_plots_from_config_with_summary

    sys.modules["nanum_pipeline_29"] = module
    return tracker


def _remove_stub_legacy() -> None:
    sys.modules.pop("nanum_pipeline_29", None)


class RunUnitaryPlotsBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracker = _install_stub_legacy()

    def tearDown(self) -> None:
        _remove_stub_legacy()

    def test_skips_when_final_table_is_none(self) -> None:
        from pipeline_newgen_rev1.bridges.legacy_runtime import RunUnitaryPlotsBridgeStage

        with tempfile.TemporaryDirectory() as tmp:
            ctx = RuntimeContext(project_root=Path(tmp))
            ctx.output_dir = Path(tmp)
            # final_table stays None
            RunUnitaryPlotsBridgeStage().run(ctx)
            self.assertIsNone(ctx.unitary_plot_summary)
            self.assertFalse((Path(tmp) / "plots").exists())

    def test_invokes_legacy_plot_function_and_stores_summary(self) -> None:
        from pipeline_newgen_rev1.bridges.legacy_runtime import RunUnitaryPlotsBridgeStage

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            ctx = RuntimeContext(project_root=out)
            ctx.output_dir = out
            ctx.final_table = pd.DataFrame({"Load_kW": [10.0], "BSFC_g_kWh": [300.0]})

            RunUnitaryPlotsBridgeStage().run(ctx)

            self.assertIsNotNone(ctx.unitary_plot_summary)
            assert ctx.unitary_plot_summary is not None
            self.assertEqual(ctx.unitary_plot_summary["generated"], 1)
            self.assertEqual(ctx.unitary_plot_summary["generated_labels"], ["BSFC_vs_Load"])
            self.assertTrue((out / "plots").exists())

            method_calls = [c[0] for c in self.tracker.mock_calls]
            self.assertIn("load_pipeline29_config_bundle", method_calls)  # bundle loaded on demand
            self.assertIn("make_plots_from_config_with_summary", method_calls)

    def test_catches_legacy_exception_gracefully(self) -> None:
        _remove_stub_legacy()
        self.tracker = _install_stub_legacy(raise_in_plot=True)

        from pipeline_newgen_rev1.bridges.legacy_runtime import RunUnitaryPlotsBridgeStage

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            ctx = RuntimeContext(project_root=out)
            ctx.output_dir = out
            ctx.final_table = pd.DataFrame({"Load_kW": [10.0]})

            # Should not raise; summary stays None.
            RunUnitaryPlotsBridgeStage().run(ctx)
            self.assertIsNone(ctx.unitary_plot_summary)


if __name__ == "__main__":
    unittest.main()
