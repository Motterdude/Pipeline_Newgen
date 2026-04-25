"""Tests for runtime/sweep_axis.py — axis resolution and rewriting."""
from __future__ import annotations

import unittest

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.runtime.sweep_axis import (
    resolve_plot_fixed_x_for_sweep,
    resolve_plot_x_for_sweep,
    resolve_plot_x_label_for_sweep,
    rewrite_plot_filename_title,
    sweep_axis_label_for_col,
    sweep_axis_token_for_col,
)


class TestSweepAxisLabelForCol(unittest.TestCase):
    def test_lambda_key(self):
        label = sweep_axis_label_for_col(
            "Sweep_Bin_Value", sweep_x_col="Lambda_mean_of_windows", sweep_key="lambda"
        )
        self.assertIn("Lambda", label)

    def test_custom_col(self):
        label = sweep_axis_label_for_col(
            "Sweep_Bin_Value", sweep_x_col="AFR_mean_of_windows", sweep_key="afr"
        )
        self.assertIn("AFR", label)

    def test_strip_suffix(self):
        label = sweep_axis_label_for_col(
            "Sweep_Bin_Value", sweep_x_col="EGR_pct_mean_of_windows", sweep_key="egr"
        )
        self.assertNotIn("mean_of_windows", label)


class TestSweepAxisTokenForCol(unittest.TestCase):
    def test_safe_name(self):
        token = sweep_axis_token_for_col(
            "Sweep_Bin_Value", sweep_x_col="Lambda_mean_of_windows", sweep_key="lambda"
        )
        self.assertTrue(token.isidentifier() or "_" in token or token.isalnum())
        self.assertNotIn(" ", token)


class TestResolvePlotXForSweep(unittest.TestCase):
    def test_load_redirected(self):
        col, overridden = resolve_plot_x_for_sweep(
            "Load_kW", sweep_active=True,
            sweep_x_col="Lambda_mean_of_windows",
            sweep_effective_x_col="Sweep_Bin_Value",
        )
        self.assertEqual(col, "Sweep_Bin_Value")
        self.assertTrue(overridden)

    def test_empty_redirected(self):
        col, overridden = resolve_plot_x_for_sweep(
            "", sweep_active=True,
            sweep_x_col="Lambda_mean_of_windows",
            sweep_effective_x_col="Sweep_Bin_Value",
        )
        self.assertEqual(col, "Sweep_Bin_Value")
        self.assertTrue(overridden)

    def test_explicit_sweep_col_redirected(self):
        col, overridden = resolve_plot_x_for_sweep(
            "Sweep_Bin_Value", sweep_active=True,
            sweep_x_col="Lambda_mean_of_windows",
            sweep_effective_x_col="Sweep_Bin_Value",
        )
        self.assertEqual(col, "Sweep_Bin_Value")
        self.assertTrue(overridden)

    def test_non_load_kept(self):
        col, overridden = resolve_plot_x_for_sweep(
            "RPM_mean", sweep_active=True,
            sweep_x_col="Lambda_mean_of_windows",
            sweep_effective_x_col="Sweep_Bin_Value",
        )
        self.assertEqual(col, "RPM_mean")
        self.assertFalse(overridden)

    def test_inactive_passthrough(self):
        col, overridden = resolve_plot_x_for_sweep(
            "Load_kW", sweep_active=False,
            sweep_x_col="Lambda_mean_of_windows",
            sweep_effective_x_col="Sweep_Bin_Value",
        )
        self.assertEqual(col, "Load_kW")
        self.assertFalse(overridden)


class TestRewritePlotFilenameTitle(unittest.TestCase):
    def test_vs_power_to_vs_token(self):
        fn, tt = rewrite_plot_filename_title(
            "CO2_pct_vs_power_all.png", "CO2 vs power (all fuels)",
            x_col_req="", x_col_resolved="Sweep_Bin_Value",
            sweep_active=True, sweep_x_col="Lambda_mean_of_windows",
            sweep_effective_x_col="Sweep_Bin_Value",
            sweep_axis_token="Lambda", sweep_axis_label="Lambda",
        )
        self.assertIn("Lambda", fn)
        self.assertNotIn("power", fn.lower())
        self.assertIn("Lambda", tt)

    def test_inactive_unchanged(self):
        fn, tt = rewrite_plot_filename_title(
            "CO2_vs_power.png", "CO2 vs power",
            x_col_req="Load_kW", x_col_resolved="Load_kW",
            sweep_active=False, sweep_x_col="",
            sweep_effective_x_col="",
            sweep_axis_token="", sweep_axis_label="",
        )
        self.assertEqual(fn, "CO2_vs_power.png")
        self.assertEqual(tt, "CO2 vs power")


class TestResolvePlotFixedXForSweep(unittest.TestCase):
    def test_nullified_for_load(self):
        result = resolve_plot_fixed_x_for_sweep(
            "Load_kW", (0.0, 100.0, 10.0),
            sweep_active=True, sweep_x_col="Lambda_mean_of_windows",
        )
        self.assertIsNone(result)

    def test_preserved_for_other(self):
        result = resolve_plot_fixed_x_for_sweep(
            "RPM_mean", (0.0, 6000.0, 500.0),
            sweep_active=True, sweep_x_col="Lambda_mean_of_windows",
        )
        self.assertEqual(result, (0.0, 6000.0, 500.0))

    def test_inactive_preserved(self):
        result = resolve_plot_fixed_x_for_sweep(
            "Load_kW", (0.0, 100.0, 10.0),
            sweep_active=False, sweep_x_col="",
        )
        self.assertEqual(result, (0.0, 100.0, 10.0))


class TestResolvePlotXLabelForSweep(unittest.TestCase):
    def test_auto_label_replaced(self):
        label = resolve_plot_x_label_for_sweep(
            "", "Load_kW", "Sweep_Bin_Value",
            sweep_active=True, sweep_x_col="Lambda_mean_of_windows",
            sweep_effective_x_col="Sweep_Bin_Value",
            sweep_axis_label="Lambda",
        )
        self.assertEqual(label, "Lambda")

    def test_custom_label_kept(self):
        label = resolve_plot_x_label_for_sweep(
            "My Custom Label", "Load_kW", "Sweep_Bin_Value",
            sweep_active=True, sweep_x_col="Lambda_mean_of_windows",
            sweep_effective_x_col="Sweep_Bin_Value",
            sweep_axis_label="Lambda",
        )
        self.assertEqual(label, "My Custom Label")


if __name__ == "__main__":
    unittest.main()
