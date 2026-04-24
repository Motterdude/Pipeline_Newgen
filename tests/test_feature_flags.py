from __future__ import annotations

import unittest

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.workflows.load_sweep.feature_flags import (
    default_feature_selection,
    merge_feature_selection,
    unknown_feature_keys,
)


class FeatureFlagsTests(unittest.TestCase):
    def test_load_defaults_keep_sweep_features_off(self) -> None:
        selection = default_feature_selection("load")
        self.assertFalse(selection["show_runtime_preflight"])
        self.assertFalse(selection["parse_sweep_metadata"])
        self.assertFalse(selection["apply_sweep_binning"])
        self.assertFalse(selection["prompt_sweep_duplicate_selector"])
        self.assertFalse(selection["rewrite_plot_axis_to_sweep"])
        self.assertTrue(selection["run_compare_plots"])
        self.assertTrue(selection["run_compare_iteracoes"])

    def test_sweep_defaults_enable_sweep_runtime(self) -> None:
        selection = default_feature_selection("sweep")
        self.assertTrue(selection["show_runtime_preflight"])
        self.assertTrue(selection["parse_sweep_metadata"])
        self.assertTrue(selection["apply_sweep_binning"])
        self.assertTrue(selection["prompt_sweep_duplicate_selector"])
        self.assertTrue(selection["rewrite_plot_axis_to_sweep"])
        self.assertFalse(selection["run_compare_plots"])
        self.assertFalse(selection["run_compare_iteracoes"])

    def test_merge_ignores_unknown_keys(self) -> None:
        selection = merge_feature_selection("load", {"apply_sweep_binning": True, "unknown_flag": True})
        self.assertTrue(selection["apply_sweep_binning"])
        self.assertEqual(["missing_flag"], unknown_feature_keys(["missing_flag"]))


if __name__ == "__main__":
    unittest.main()

