"""Tests for the native unitary-plots subpackage."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd


class TestFuelGroups(unittest.TestCase):
    """Tests for runtime.unitary_plots.fuel_groups."""

    def _sample_df(self):
        return pd.DataFrame({
            "Load_kW": [10, 20, 30, 10, 20, 30, 10, 20, 30],
            "EtOH_pct": [94, 94, 94, 75, 75, 75, 65, 65, 65],
            "H2O_pct": [6, 6, 6, 25, 25, 25, 35, 35, 35],
            "DIES_pct": [0, 0, 0, 0, 0, 0, 0, 0, 0],
            "BIOD_pct": [0, 0, 0, 0, 0, 0, 0, 0, 0],
            "Y_val": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0],
        })

    def test_fuel_plot_groups_labels(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.fuel_groups import fuel_plot_groups
        df = self._sample_df()
        groups = fuel_plot_groups(df)
        labels = [label for label, _ in groups]
        self.assertIn("E94H6", labels)
        self.assertIn("E75H25", labels)
        self.assertIn("E65H35", labels)

    def test_preferred_order(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.fuel_groups import _preferred_fuel_label_order
        result = _preferred_fuel_label_order(["E65H35", "E94H6", "D85B15", "Custom"])
        self.assertEqual(result[:3], ["D85B15", "E94H6", "E65H35"])
        self.assertIn("Custom", result)

    def test_fuel_plot_groups_filter_h2o(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.fuel_groups import fuel_plot_groups
        df = self._sample_df()
        groups = fuel_plot_groups(df, fuels_override=[6])
        labels = [label for label, _ in groups]
        self.assertIn("E94H6", labels)
        self.assertNotIn("E75H25", labels)

    def test_series_fuel_plot_groups_no_series(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.fuel_groups import series_fuel_plot_groups
        df = self._sample_df()
        groups = series_fuel_plot_groups(df, series_col=None)
        self.assertTrue(len(groups) >= 1)

    def test_series_fuel_plot_groups_with_series(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.fuel_groups import series_fuel_plot_groups
        df = self._sample_df()
        df["SourceFolder"] = ["A", "A", "A", "B", "B", "B", "A", "A", "A"]
        groups = series_fuel_plot_groups(df, series_col="SourceFolder")
        labels = [label for label, _ in groups]
        self.assertTrue(any("|" in (label or "") for label in labels))

    def test_expand_legacy_filter_includes_diesel(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.fuel_groups import _expand_legacy_all_fuels_filter
        df = pd.DataFrame({"H2O_pct": [0, 6, 25, 35]})
        result = _expand_legacy_all_fuels_filter(df, [6, 25, 35])
        self.assertIn(0, result)


class TestConfigParsing(unittest.TestCase):
    """Tests for runtime.unitary_plots.config_parsing."""

    def test_parse_axis_spec_valid(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _parse_axis_spec
        result = _parse_axis_spec("0", "100", "10")
        self.assertEqual(result, (0.0, 100.0, 10.0))

    def test_parse_axis_spec_nan(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _parse_axis_spec
        result = _parse_axis_spec("0", "nan", "10")
        self.assertIsNone(result)

    def test_parse_axis_value_with_unit(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _parse_axis_value
        result = _parse_axis_value("1013.25mbar", target_unit="pa")
        self.assertAlmostEqual(result, 101325.0, places=0)

    def test_parse_axis_value_auto(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _parse_axis_value
        result = _parse_axis_value("auto")
        self.assertTrue(np.isnan(result))

    def test_row_enabled_truthy(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _row_enabled
        self.assertTrue(_row_enabled("1"))
        self.assertTrue(_row_enabled("true"))
        self.assertTrue(_row_enabled("yes"))
        self.assertFalse(_row_enabled("0"))
        self.assertFalse(_row_enabled(None))
        self.assertFalse(_row_enabled(pd.NA))

    def test_parse_csv_list_ints(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _parse_csv_list_ints
        self.assertEqual(_parse_csv_list_ints("0,6,25,35"), [0, 6, 25, 35])
        self.assertIsNone(_parse_csv_list_ints(pd.NA))
        self.assertIsNone(_parse_csv_list_ints(""))

    def test_strip_leading_raw_plot_name(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _strip_leading_raw_plot_name
        self.assertEqual(_strip_leading_raw_plot_name("raw_test.png"), "test.png")
        self.assertEqual(_strip_leading_raw_plot_name("test.png"), "test.png")

    def test_derive_filename_for_expansion(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _derive_filename_for_expansion
        result = _derive_filename_for_expansion("kibox_all.png", "KIBOX_Pmax")
        self.assertIn("KIBOX_Pmax", result)
        self.assertTrue(result.endswith(".png"))

    def test_resolve_plot_x_request(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _resolve_plot_x_request
        col, mestrado = _resolve_plot_x_request("")
        self.assertEqual(col, "Load_kW")
        self.assertFalse(mestrado)
        col2, _ = _resolve_plot_x_request("RPM")
        self.assertEqual(col2, "RPM")

    def test_mapping_unit_for_y_col(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _mapping_unit_for_y_col
        mappings = {"consumo_kg_h": {"mean": "Consumo_kg_h_mean", "unit": "kg/h"}}
        result = _mapping_unit_for_y_col("Consumo_kg_h_mean", mappings)
        self.assertEqual(result, "kg/h")

    def test_mapping_unit_returns_none(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _mapping_unit_for_y_col
        result = _mapping_unit_for_y_col("nonexistent", {})
        self.assertIsNone(result)


class TestUncertainty(unittest.TestCase):
    """Tests for uncertainty-related config_parsing functions."""

    def test_plot_uncertainty_variants_default(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _plot_uncertainty_variants
        row = pd.Series({})
        variants = _plot_uncertainty_variants(row)
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0][0], "with_uncertainty")

    def test_plot_uncertainty_variants_both(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _plot_uncertainty_variants
        row = pd.Series({"with_uncertainty": "1", "without_uncertainty": "1"})
        variants = _plot_uncertainty_variants(row)
        self.assertEqual(len(variants), 2)

    def test_decorate_variant_output_dual(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _decorate_plot_variant_output
        fn, tt = _decorate_plot_variant_output("test.png", "Test", "with_uncertainty", True)
        self.assertIn("with_uncertainty", fn)
        self.assertIn("with uncertainty", tt)

    def test_decorate_variant_output_single(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _decorate_plot_variant_output
        fn, tt = _decorate_plot_variant_output("test.png", "Test", "with_uncertainty", False)
        self.assertEqual(fn, "test.png")
        self.assertEqual(tt, "Test")

    def test_guess_uncertainty_col(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _guess_plot_uncertainty_col
        df = pd.DataFrame({"Y_val": [1, 2], "U_Y_val": [0.1, 0.2]})
        result = _guess_plot_uncertainty_col(df, "Y_val", {})
        self.assertEqual(result, "U_Y_val")

    def test_guess_uncertainty_col_missing(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _guess_plot_uncertainty_col
        df = pd.DataFrame({"Y_val": [1, 2]})
        result = _guess_plot_uncertainty_col(df, "Y_val", {})
        self.assertIsNone(result)

    def test_yerr_disabled_token(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _yerr_disabled_token
        self.assertTrue(_yerr_disabled_token("off"))
        self.assertTrue(_yerr_disabled_token("none"))
        self.assertFalse(_yerr_disabled_token("U_val"))

    def test_shared_y_limits(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.config_parsing import _shared_plot_y_limits_for_variants
        df = pd.DataFrame({
            "X": [1, 2, 3],
            "Y": [10, 20, 30],
            "EtOH_pct": [94, 94, 94],
            "H2O_pct": [6, 6, 6],
            "DIES_pct": [0, 0, 0],
            "BIOD_pct": [0, 0, 0],
        })
        result = _shared_plot_y_limits_for_variants(
            df, x_col="X", y_col="Y", variant_yerr_cols=[None]
        )
        self.assertIsNotNone(result)
        ymin, ymax = result
        self.assertLess(ymin, 10)
        self.assertGreater(ymax, 30)


class TestRenderers(unittest.TestCase):
    """Tests for runtime.unitary_plots.renderers."""

    def _sample_df(self):
        return pd.DataFrame({
            "Load_kW": [10, 20, 30],
            "Y_val": [1.0, 2.0, 3.0],
            "EtOH_pct": [94, 94, 94],
            "H2O_pct": [6, 6, 6],
            "DIES_pct": [0, 0, 0],
            "BIOD_pct": [0, 0, 0],
        })

    def test_plot_all_fuels_generates_png(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.renderers import plot_all_fuels
        with tempfile.TemporaryDirectory() as tmpdir:
            ok = plot_all_fuels(
                self._sample_df(),
                y_col="Y_val",
                yerr_col=None,
                title="Test",
                filename="test_plot.png",
                y_label="Y",
                plot_dir=Path(tmpdir),
            )
            self.assertTrue(ok)
            png_path = Path(tmpdir) / "test_plot.png"
            self.assertTrue(png_path.exists())
            self.assertGreater(png_path.stat().st_size, 0)

    def test_plot_all_fuels_empty_returns_false(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.renderers import plot_all_fuels
        empty_df = pd.DataFrame({"Load_kW": [], "Y_val": []})
        with tempfile.TemporaryDirectory() as tmpdir:
            ok = plot_all_fuels(
                empty_df,
                y_col="Y_val",
                yerr_col=None,
                title="Empty",
                filename="empty.png",
                y_label="Y",
                plot_dir=Path(tmpdir),
            )
            self.assertFalse(ok)

    def test_plot_all_fuels_xy_generates_png(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.renderers import plot_all_fuels_xy
        with tempfile.TemporaryDirectory() as tmpdir:
            ok = plot_all_fuels_xy(
                self._sample_df(),
                x_col="Load_kW",
                y_col="Y_val",
                yerr_col=None,
                title="Test XY",
                filename="test_xy.png",
                x_label="X",
                y_label="Y",
                plot_dir=Path(tmpdir),
            )
            self.assertTrue(ok)
            self.assertTrue((Path(tmpdir) / "test_xy.png").exists())

    def test_plot_all_fuels_with_labels_generates_png(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.renderers import plot_all_fuels_with_value_labels
        with tempfile.TemporaryDirectory() as tmpdir:
            ok = plot_all_fuels_with_value_labels(
                self._sample_df(),
                y_col="Y_val",
                title="Test Labels",
                filename="test_labels.png",
                y_label="Y",
                label_variant="box",
                plot_dir=Path(tmpdir),
            )
            self.assertTrue(ok)
            self.assertTrue((Path(tmpdir) / "test_labels.png").exists())

    def test_plot_with_errorbar(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.renderers import plot_all_fuels
        df = self._sample_df()
        df["U_Y_val"] = [0.1, 0.2, 0.3]
        with tempfile.TemporaryDirectory() as tmpdir:
            ok = plot_all_fuels(
                df,
                y_col="Y_val",
                yerr_col="U_Y_val",
                title="Test Errorbar",
                filename="test_err.png",
                y_label="Y",
                plot_dir=Path(tmpdir),
            )
            self.assertTrue(ok)

    def test_plot_with_fixed_axes(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.renderers import plot_all_fuels
        with tempfile.TemporaryDirectory() as tmpdir:
            ok = plot_all_fuels(
                self._sample_df(),
                y_col="Y_val",
                yerr_col=None,
                title="Fixed Axes",
                filename="test_fixed.png",
                y_label="Y",
                fixed_x=(0, 50, 10),
                fixed_y=(0, 5, 1),
                plot_dir=Path(tmpdir),
            )
            self.assertTrue(ok)

    def test_plot_with_tolerance(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.renderers import plot_all_fuels
        with tempfile.TemporaryDirectory() as tmpdir:
            ok = plot_all_fuels(
                self._sample_df(),
                y_col="Y_val",
                yerr_col=None,
                title="Tolerance",
                filename="test_tol.png",
                y_label="Y",
                y_tol_plus=5.0,
                y_tol_minus=5.0,
                plot_dir=Path(tmpdir),
            )
            self.assertTrue(ok)


class TestDispatch(unittest.TestCase):
    """Tests for runtime.unitary_plots.dispatch."""

    def _sample_df(self):
        return pd.DataFrame({
            "Load_kW": [10, 20, 30],
            "Y_val": [1.0, 2.0, 3.0],
            "EtOH_pct": [94, 94, 94],
            "H2O_pct": [6, 6, 6],
            "DIES_pct": [0, 0, 0],
            "BIOD_pct": [0, 0, 0],
        })

    def test_dispatch_all_fuels(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.dispatch import make_plots_from_config_with_summary
        plots_df = pd.DataFrame([{
            "enabled": "1",
            "plot_type": "all_fuels_yx",
            "filename": "test_dispatch.png",
            "title": "Test",
            "x_col": "Load_kW",
            "y_col": "Y_val",
            "x_label": "Power",
            "y_label": "Y",
            "x_min": "nan", "x_max": "nan", "x_step": "nan",
            "y_min": "nan", "y_max": "nan", "y_step": "nan",
            "y_tol_plus": "0", "y_tol_minus": "0",
            "filter_h2o_list": "",
            "with_uncertainty": "", "without_uncertainty": "",
        }])
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = make_plots_from_config_with_summary(
                self._sample_df(), plots_df, {}, plot_dir=Path(tmpdir)
            )
            self.assertEqual(summary["generated"], 1)
            self.assertEqual(summary["skipped"], 0)

    def test_dispatch_disabled_row(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.dispatch import make_plots_from_config_with_summary
        plots_df = pd.DataFrame([{
            "enabled": "0",
            "plot_type": "all_fuels_yx",
            "filename": "skip.png",
            "y_col": "Y_val",
        }])
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = make_plots_from_config_with_summary(
                self._sample_df(), plots_df, {}, plot_dir=Path(tmpdir)
            )
            self.assertEqual(summary["disabled"], 1)
            self.assertEqual(summary["generated"], 0)

    def test_dispatch_empty_plots_df(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.dispatch import make_plots_from_config_with_summary
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = make_plots_from_config_with_summary(
                self._sample_df(), pd.DataFrame(), {}, plot_dir=Path(tmpdir)
            )
            self.assertEqual(summary["generated"], 0)

    def test_dispatch_missing_y_col(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.dispatch import make_plots_from_config_with_summary
        plots_df = pd.DataFrame([{
            "enabled": "1",
            "plot_type": "all_fuels_yx",
            "filename": "missing_y.png",
            "x_col": "Load_kW",
            "y_col": "NONEXISTENT",
        }])
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = make_plots_from_config_with_summary(
                self._sample_df(), plots_df, {}, plot_dir=Path(tmpdir)
            )
            self.assertEqual(summary["skipped"], 1)

    def test_dispatch_labels_type(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.dispatch import make_plots_from_config_with_summary
        plots_df = pd.DataFrame([{
            "enabled": "1",
            "plot_type": "labels",
            "filename": "test_labels.png",
            "title": "Labels",
            "x_col": "Load_kW",
            "y_col": "Y_val",
            "x_label": "X", "y_label": "Y",
            "x_min": "nan", "x_max": "nan", "x_step": "nan",
            "y_min": "nan", "y_max": "nan", "y_step": "nan",
            "y_tol_plus": "0", "y_tol_minus": "0",
            "filter_h2o_list": "",
            "label_variant": "box",
        }])
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = make_plots_from_config_with_summary(
                self._sample_df(), plots_df, {}, plot_dir=Path(tmpdir)
            )
            self.assertEqual(summary["generated"], 1)

    def test_dispatch_unknown_plot_type(self):
        from pipeline_newgen_rev1.runtime.unitary_plots.dispatch import make_plots_from_config_with_summary
        plots_df = pd.DataFrame([{
            "enabled": "1",
            "plot_type": "unknown_type",
            "filename": "unknown.png",
        }])
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = make_plots_from_config_with_summary(
                self._sample_df(), plots_df, {}, plot_dir=Path(tmpdir)
            )
            self.assertEqual(summary["skipped"], 1)


class TestRunUnitaryPlotsStage(unittest.TestCase):
    """Tests for the native RunUnitaryPlotsStage."""

    def test_feature_key(self):
        from pipeline_newgen_rev1.runtime.stages.run_unitary_plots import RunUnitaryPlotsStage
        stage = RunUnitaryPlotsStage()
        self.assertEqual(stage.feature_key, "run_unitary_plots")

    def test_skips_when_no_final_table(self):
        from pipeline_newgen_rev1.runtime.stages.run_unitary_plots import RunUnitaryPlotsStage
        ctx = MagicMock()
        ctx.final_table = None
        stage = RunUnitaryPlotsStage()
        stage.run(ctx)
        self.assertIsNone(ctx.final_table)

    def test_runs_with_data(self):
        from pipeline_newgen_rev1.runtime.stages.run_unitary_plots import RunUnitaryPlotsStage
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = MagicMock()
            ctx.final_table = pd.DataFrame({
                "Load_kW": [10, 20],
                "Y_val": [1.0, 2.0],
                "EtOH_pct": [94, 94],
                "H2O_pct": [6, 6],
                "DIES_pct": [0, 0],
                "BIOD_pct": [0, 0],
            })
            ctx.output_dir = Path(tmpdir)
            ctx.bundle = MagicMock()
            ctx.bundle.plots = [{
                "enabled": "1",
                "plot_type": "all_fuels_yx",
                "filename": "test.png",
                "title": "Test",
                "x_col": "Load_kW",
                "y_col": "Y_val",
                "x_label": "X", "y_label": "Y",
                "x_min": "nan", "x_max": "nan", "x_step": "nan",
                "y_min": "nan", "y_max": "nan", "y_step": "nan",
                "y_tol_plus": "0", "y_tol_minus": "0",
                "filter_h2o_list": "",
                "with_uncertainty": "", "without_uncertainty": "",
            }]
            ctx.bundle.mappings = {}
            ctx.sweep_active = False
            ctx.sweep_effective_x_col = ""
            ctx.sweep_axis_label = ""
            ctx.sweep_axis_token = ""
            ctx.normalized_state = None
            stage = RunUnitaryPlotsStage()
            stage.run(ctx)
            self.assertIsNotNone(ctx.unitary_plot_summary)
            self.assertTrue((Path(tmpdir) / "plots" / "test.png").exists())


if __name__ == "__main__":
    unittest.main()
