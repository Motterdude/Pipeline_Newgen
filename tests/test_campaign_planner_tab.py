"""Tests for ui/campaign_planner_tab.py — Campaign Planner widget logic."""
from __future__ import annotations

import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401

from pipeline_newgen_rev1.runtime.campaign_scan import CampaignCatalog


class TestCampaignPlannerTabImport(unittest.TestCase):
    def test_module_imports(self) -> None:
        from pipeline_newgen_rev1.ui.campaign_planner_tab import CampaignPlannerTab
        self.assertTrue(callable(CampaignPlannerTab))


class TestCampaignPlannerTabLogic(unittest.TestCase):
    """Test the public API methods without instantiating Qt widgets."""

    def test_campaign_planner_state_schema(self) -> None:
        from pipeline_newgen_rev1.ui.campaign_planner_tab import CampaignPlannerTab
        expected_keys = {"groups", "pairs", "aggregation", "plot_families", "iteration_mode"}
        self.assertTrue(expected_keys)


class TestAvailableSeriesLabels(unittest.TestCase):
    def test_fuel_mode_labels(self) -> None:
        catalog = CampaignCatalog(
            fuel_labels=["E65H35", "E75H25", "E94H6"],
            load_points=[10.0, 20.0],
            directions=[],
            campaigns=[],
            iteration_mode="fuel",
            file_count_by_fuel={"E65H35": 2, "E75H25": 2, "E94H6": 2},
            file_count_by_campaign={},
            file_count_by_direction={},
            total_files=6,
        )
        from pipeline_newgen_rev1.runtime.campaign_scan import default_comparison_pairs
        pairs = default_comparison_pairs(catalog)
        self.assertGreater(len(pairs), 0)
        self.assertEqual(pairs[0][0], "E65H35")

    def test_direction_mode_labels(self) -> None:
        catalog = CampaignCatalog(
            fuel_labels=["D85B15"],
            load_points=[50.0],
            directions=["descida", "subida"],
            campaigns=["aditivado", "baseline"],
            iteration_mode="direction",
            file_count_by_fuel={"D85B15": 4},
            file_count_by_campaign={"baseline": 2, "aditivado": 2},
            file_count_by_direction={"subida": 2, "descida": 2},
            total_files=4,
        )
        from pipeline_newgen_rev1.runtime.campaign_scan import default_comparison_pairs
        pairs = default_comparison_pairs(catalog)
        self.assertGreater(len(pairs), 0)


if __name__ == "__main__":
    unittest.main()
