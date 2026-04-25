"""Tests for the compare_plots grouping module (subida x descida within campaign)."""
from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from _path import ROOT  # noqa: F401

from pipeline_newgen_rev1.runtime.compare_plots import (
    _compare_group_key_from_source_folder,
    _infer_source_direction_from_folder_name,
    _normalize_compare_series_name,
    _safe_folder_name,
    iter_compare_plot_groups,
)


class TestNormalizeCompareSeriesName(unittest.TestCase):
    def test_subindo_becomes_subida(self) -> None:
        self.assertIn("subida", _normalize_compare_series_name("test / subindo"))

    def test_descendo_becomes_descida(self) -> None:
        self.assertIn("descida", _normalize_compare_series_name("test / descendo"))

    def test_empty_returns_fallback(self) -> None:
        self.assertEqual(_normalize_compare_series_name(""), "origem_desconhecida")


class TestInferDirection(unittest.TestCase):
    def test_subindo(self) -> None:
        self.assertEqual(_infer_source_direction_from_folder_name("test / subindo"), "subindo")

    def test_descendo(self) -> None:
        self.assertEqual(_infer_source_direction_from_folder_name("test / descendo"), "descendo")

    def test_subida_variant(self) -> None:
        self.assertEqual(_infer_source_direction_from_folder_name("test / subida"), "subindo")

    def test_up_english(self) -> None:
        self.assertEqual(_infer_source_direction_from_folder_name("test / up"), "subindo")

    def test_down_english(self) -> None:
        self.assertEqual(_infer_source_direction_from_folder_name("test / down"), "descendo")

    def test_neutral(self) -> None:
        self.assertIsNone(_infer_source_direction_from_folder_name("test / something"))


class TestCompareGroupKey(unittest.TestCase):
    def test_strips_direction(self) -> None:
        key = _compare_group_key_from_source_folder("baseline / subindo")
        self.assertNotIn("subindo", key)
        self.assertIn("baseline", key)

    def test_empty_returns_empty(self) -> None:
        self.assertEqual(_compare_group_key_from_source_folder(""), "")


class TestSafeFolderName(unittest.TestCase):
    def test_unsafe_chars_replaced(self) -> None:
        result = _safe_folder_name('test<>:"/\\|?*name')
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)

    def test_empty_returns_compare(self) -> None:
        self.assertEqual(_safe_folder_name(""), "compare")


class TestIterComparePlotGroups(unittest.TestCase):
    def test_empty_df(self) -> None:
        self.assertEqual(iter_compare_plot_groups(pd.DataFrame()), [])

    def test_no_basename(self) -> None:
        df = pd.DataFrame({"X": [1, 2]})
        self.assertEqual(iter_compare_plot_groups(df), [])

    def test_single_direction_no_pair(self) -> None:
        df = pd.DataFrame({"BaseName": [
            "campanha1__subindo__file1",
            "campanha1__subindo__file2",
        ]})
        self.assertEqual(iter_compare_plot_groups(df), [])

    def test_matching_pair(self) -> None:
        df = pd.DataFrame({
            "BaseName": [
                "campanha1__subindo__file1",
                "campanha1__descendo__file2",
            ],
            "Load_kW": [10.0, 20.0],
        })
        groups = iter_compare_plot_groups(df, root=Path("/tmp/test_plots"))
        self.assertEqual(len(groups), 1)
        gk, plot_dir, group_df = groups[0]
        self.assertTrue(gk)
        self.assertIn("compare", str(plot_dir))
        self.assertIn("_COMPARE_SERIES", group_df.columns)
        self.assertIn("_COMPARE_DIRECTION", group_df.columns)

    def test_multiple_campaigns(self) -> None:
        df = pd.DataFrame({
            "BaseName": [
                "camp_a__subindo__f1",
                "camp_a__descendo__f2",
                "camp_b__subindo__f3",
                "camp_b__descendo__f4",
            ],
            "Load_kW": [10.0, 20.0, 10.0, 20.0],
        })
        groups = iter_compare_plot_groups(df, root=Path("/tmp/plots"))
        self.assertEqual(len(groups), 2)


class TestStageRegistry(unittest.TestCase):
    def test_run_compare_plots_in_registry(self) -> None:
        from pipeline_newgen_rev1.runtime.stages import STAGE_REGISTRY, PLOTTING_STAGE_ORDER
        self.assertIn("run_compare_plots", STAGE_REGISTRY)
        self.assertIn("run_compare_plots", PLOTTING_STAGE_ORDER)

    def test_run_special_load_plots_in_registry(self) -> None:
        from pipeline_newgen_rev1.runtime.stages import STAGE_REGISTRY, PLOTTING_STAGE_ORDER
        self.assertIn("run_special_load_plots", STAGE_REGISTRY)
        self.assertIn("run_special_load_plots", PLOTTING_STAGE_ORDER)

    def test_twenty_stages_total(self) -> None:
        from pipeline_newgen_rev1.runtime.stages import STAGE_REGISTRY
        self.assertEqual(len(STAGE_REGISTRY), 20)


if __name__ == "__main__":
    unittest.main()
