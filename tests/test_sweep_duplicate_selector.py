"""Tests for runtime/sweep_duplicate_selector.py — catalog building and filtering."""
from __future__ import annotations

import unittest

import pandas as pd

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.runtime.sweep_duplicate_selector import (
    apply_sweep_duplicate_filter,
    build_sweep_duplicate_catalog,
    prompt_sweep_duplicate_selector,
)


class TestBuildSweepDuplicateCatalog(unittest.TestCase):
    def test_basic(self):
        df = pd.DataFrame({
            "Sweep_Bin_Value": [1.0, 1.0, 2.0],
            "EtOH_pct": [94, 94, 94],
            "H2O_pct": [6, 6, 6],
            "DIES_pct": [0, 0, 0],
            "BIOD_pct": [0, 0, 0],
            "BaseName": ["a.tdms", "b.tdms", "c.tdms"],
        })
        fuel_labels, sweep_vals, catalog = build_sweep_duplicate_catalog(df, x_col="Sweep_Bin_Value")
        self.assertGreaterEqual(len(catalog), 1)

    def test_empty_df(self):
        df = pd.DataFrame({
            "Sweep_Bin_Value": pd.Series(dtype=float),
            "EtOH_pct": pd.Series(dtype=float),
            "H2O_pct": pd.Series(dtype=float),
            "DIES_pct": pd.Series(dtype=float),
            "BIOD_pct": pd.Series(dtype=float),
            "BaseName": pd.Series(dtype=str),
        })
        fuel_labels, sweep_vals, catalog = build_sweep_duplicate_catalog(df, x_col="Sweep_Bin_Value")
        self.assertEqual(len(catalog), 0)

    def test_no_duplicates_single_basename_per_cell(self):
        df = pd.DataFrame({
            "Sweep_Bin_Value": [1.0, 2.0, 3.0],
            "EtOH_pct": [94, 94, 94],
            "H2O_pct": [6, 6, 6],
            "DIES_pct": [0, 0, 0],
            "BIOD_pct": [0, 0, 0],
            "BaseName": ["a.tdms", "b.tdms", "c.tdms"],
        })
        _, _, catalog = build_sweep_duplicate_catalog(df, x_col="Sweep_Bin_Value")
        for key, basenames in catalog.items():
            self.assertEqual(len(basenames), 1)


class TestApplySweepDuplicateFilter(unittest.TestCase):
    def test_keeps_selected(self):
        df = pd.DataFrame({
            "BaseName": ["a.tdms", "b.tdms", "c.tdms"],
            "val": [1, 2, 3],
        })
        result = apply_sweep_duplicate_filter(df, {"a.tdms", "c.tdms"})
        self.assertEqual(len(result), 2)
        self.assertEqual(set(result["BaseName"]), {"a.tdms", "c.tdms"})

    def test_none_passthrough(self):
        df = pd.DataFrame({"BaseName": ["a", "b"], "val": [1, 2]})
        result = apply_sweep_duplicate_filter(df, None)
        self.assertEqual(len(result), 2)


class TestPromptSweepDuplicateSelector(unittest.TestCase):
    def test_no_duplicates_returns_none(self):
        df = pd.DataFrame({
            "Sweep_Bin_Value": [1.0, 2.0],
            "EtOH_pct": [94, 94],
            "H2O_pct": [6, 6],
            "DIES_pct": [0, 0],
            "BIOD_pct": [0, 0],
            "BaseName": ["a.tdms", "b.tdms"],
        })
        result = prompt_sweep_duplicate_selector(df, x_col="Sweep_Bin_Value", axis_label="Lambda")
        self.assertIsNone(result)

    def test_injectable_func(self):
        df = pd.DataFrame({
            "Sweep_Bin_Value": [1.0, 1.0],
            "EtOH_pct": [94, 94],
            "H2O_pct": [6, 6],
            "DIES_pct": [0, 0],
            "BIOD_pct": [0, 0],
            "BaseName": ["a.tdms", "b.tdms"],
        })

        def pick_first(fuel_labels, sweep_values, catalog):
            selected = set()
            for key, basenames in catalog.items():
                if basenames:
                    selected.add(basenames[0])
            return selected

        result = prompt_sweep_duplicate_selector(
            df, x_col="Sweep_Bin_Value", axis_label="Lambda", prompt_func=pick_first
        )
        self.assertIsNotNone(result)
        self.assertIn("a.tdms", result)


if __name__ == "__main__":
    unittest.main()
