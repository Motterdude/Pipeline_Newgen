"""Tests for runtime/sweep_binning.py — sweep value clustering and bin assignment."""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.runtime.sweep_binning import (
    apply_sweep_binning,
    cluster_sweep_bin_centers,
    format_sweep_bin_label,
    _assign_value_to_sweep_bin,
    _sorted_unique_finite_values,
)


class TestFormatSweepBinLabel(unittest.TestCase):
    def test_integer(self):
        self.assertEqual(format_sweep_bin_label(100.0), "100")

    def test_decimal(self):
        self.assertEqual(format_sweep_bin_label(0.95), "0.95")

    def test_nan(self):
        self.assertEqual(format_sweep_bin_label(float("nan")), "")

    def test_none(self):
        self.assertEqual(format_sweep_bin_label(None), "")

    def test_negative(self):
        self.assertEqual(format_sweep_bin_label(-3.5), "-3.5")


class TestSortedUniqueFiniteValues(unittest.TestCase):
    def test_basic(self):
        s = pd.Series([3.0, 1.0, 2.0, 1.0, np.nan])
        result = _sorted_unique_finite_values(s)
        self.assertEqual(result, [1.0, 2.0, 3.0])

    def test_empty(self):
        self.assertEqual(_sorted_unique_finite_values(pd.Series(dtype=float)), [])


class TestClusterSweepBinCenters(unittest.TestCase):
    def test_single_value(self):
        centers = cluster_sweep_bin_centers(pd.Series([1.0]), 0.5)
        self.assertEqual(len(centers), 1)
        self.assertAlmostEqual(centers[0], 1.0)

    def test_within_tol(self):
        centers = cluster_sweep_bin_centers(pd.Series([1.0, 1.02, 1.04]), 0.1)
        self.assertEqual(len(centers), 1)

    def test_outside_tol(self):
        centers = cluster_sweep_bin_centers(pd.Series([1.0, 5.0]), 0.1)
        self.assertEqual(len(centers), 2)

    def test_empty(self):
        self.assertEqual(cluster_sweep_bin_centers(pd.Series(dtype=float), 0.5), [])

    def test_zero_tol(self):
        centers = cluster_sweep_bin_centers(pd.Series([1.0, 1.0, 2.0]), 0.0)
        self.assertEqual(len(centers), 2)

    def test_multiple_clusters(self):
        values = pd.Series([1.0, 1.01, 1.02, 5.0, 5.01, 5.02, 10.0])
        centers = cluster_sweep_bin_centers(values, 0.1)
        self.assertEqual(len(centers), 3)


class TestAssignValueToSweepBin(unittest.TestCase):
    def test_exact_match(self):
        result = _assign_value_to_sweep_bin(5.0, centers=[1.0, 5.0, 10.0], tol=0.5)
        self.assertAlmostEqual(result, 5.0)

    def test_within_tol(self):
        result = _assign_value_to_sweep_bin(5.1, centers=[1.0, 5.0, 10.0], tol=0.5)
        self.assertAlmostEqual(result, 5.0)

    def test_nan_returns_nan(self):
        result = _assign_value_to_sweep_bin(float("nan"), centers=[1.0, 5.0], tol=0.5)
        self.assertTrue(np.isnan(result))


class TestApplySweepBinning(unittest.TestCase):
    def test_adds_columns_active(self):
        df = pd.DataFrame({
            "Lambda_mean_of_windows": [0.95, 0.96, 1.05, 1.06],
            "EtOH_pct": [94, 94, 94, 94],
        })
        result = apply_sweep_binning(df, x_col="Lambda_mean_of_windows", tol=0.05, sweep_active=True)
        self.assertIn("Sweep_Bin_Value", result.columns)
        self.assertIn("Sweep_Bin_Label", result.columns)
        self.assertEqual(len(result), 4)

    def test_inactive_passthrough(self):
        df = pd.DataFrame({"Load_kW": [10, 20, 30]})
        result = apply_sweep_binning(df, x_col="Load_kW", tol=0.5, sweep_active=False)
        self.assertIn("Sweep_Bin_Value", result.columns)
        vals = result["Sweep_Bin_Value"].tolist()
        self.assertEqual(vals, [10.0, 20.0, 30.0])

    def test_empty_df(self):
        df = pd.DataFrame({"x": pd.Series(dtype=float)})
        result = apply_sweep_binning(df, x_col="x", tol=0.5, sweep_active=True)
        self.assertIn("Sweep_Bin_Value", result.columns)
        self.assertEqual(len(result), 0)

    def test_missing_x_col_returns_unchanged(self):
        df = pd.DataFrame({"other": [1, 2]})
        result = apply_sweep_binning(df, x_col="missing_col", tol=0.5, sweep_active=True)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
