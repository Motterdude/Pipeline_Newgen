"""Tests for the 4 sweep-mode stages + registry integration."""
from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.runtime.context import RuntimeContext


class TestParseSweepMetadataStage(unittest.TestCase):
    def test_sets_sweep_active_for_sweep_mode(self):
        from unittest.mock import MagicMock
        from pipeline_newgen_rev1.runtime.stages.parse_sweep_metadata import ParseSweepMetadataStage

        ctx = MagicMock()
        ctx.normalized_state = MagicMock()
        ctx.normalized_state.selection = MagicMock()
        ctx.normalized_state.selection.aggregation_mode = "sweep"
        ctx.normalized_state.selection.sweep_key = "lambda"
        ctx.labview_frames = [
            pd.DataFrame({"Sweep_Key": ["lambda"], "val": [1.0]}),
        ]
        ctx.motec_frames = []
        stage = ParseSweepMetadataStage()
        stage.run(ctx)
        self.assertTrue(ctx.sweep_active)

    def test_inactive_for_load_mode(self):
        from unittest.mock import MagicMock
        from pipeline_newgen_rev1.runtime.stages.parse_sweep_metadata import ParseSweepMetadataStage

        ctx = MagicMock()
        ctx.normalized_state = MagicMock()
        ctx.normalized_state.selection = MagicMock()
        ctx.normalized_state.selection.aggregation_mode = "load"
        stage = ParseSweepMetadataStage()
        stage.run(ctx)
        self.assertFalse(ctx.sweep_active)

    def test_feature_key(self):
        from pipeline_newgen_rev1.runtime.stages.parse_sweep_metadata import ParseSweepMetadataStage
        self.assertEqual(ParseSweepMetadataStage().feature_key, "parse_sweep_metadata")


class TestApplySweepBinningStage(unittest.TestCase):
    def test_adds_columns(self):
        from unittest.mock import MagicMock
        from pipeline_newgen_rev1.runtime.stages.apply_sweep_binning import ApplySweepBinningStage

        ctx = MagicMock()
        ctx.final_table = pd.DataFrame({
            "Lambda_mean_of_windows": [0.95, 0.96, 1.05],
        })
        ctx.sweep_active = True
        ctx.normalized_state = MagicMock()
        ctx.normalized_state.selection = MagicMock()
        ctx.normalized_state.selection.sweep_x_col = "Lambda_mean_of_windows"
        ctx.normalized_state.selection.sweep_bin_tol = 0.05

        stage = ApplySweepBinningStage()
        stage.run(ctx)
        self.assertIn("Sweep_Bin_Value", ctx.final_table.columns)

    def test_skips_when_no_final_table(self):
        from unittest.mock import MagicMock
        from pipeline_newgen_rev1.runtime.stages.apply_sweep_binning import ApplySweepBinningStage

        ctx = MagicMock()
        ctx.final_table = None
        stage = ApplySweepBinningStage()
        stage.run(ctx)

    def test_feature_key(self):
        from pipeline_newgen_rev1.runtime.stages.apply_sweep_binning import ApplySweepBinningStage
        self.assertEqual(ApplySweepBinningStage().feature_key, "apply_sweep_binning")


class TestRewritePlotAxisToSweepStage(unittest.TestCase):
    def test_populates_ctx_fields(self):
        from unittest.mock import MagicMock
        from pipeline_newgen_rev1.runtime.stages.rewrite_plot_axis_to_sweep import RewritePlotAxisToSweepStage

        ctx = MagicMock()
        ctx.sweep_active = True
        ctx.normalized_state = MagicMock()
        ctx.normalized_state.selection = MagicMock()
        ctx.normalized_state.selection.sweep_x_col = "Lambda_mean_of_windows"
        ctx.normalized_state.selection.sweep_key = "lambda"

        stage = RewritePlotAxisToSweepStage()
        stage.run(ctx)
        self.assertTrue(ctx.sweep_effective_x_col)

    def test_skips_when_inactive(self):
        from unittest.mock import MagicMock
        from pipeline_newgen_rev1.runtime.stages.rewrite_plot_axis_to_sweep import RewritePlotAxisToSweepStage

        ctx = MagicMock()
        ctx.sweep_active = False
        stage = RewritePlotAxisToSweepStage()
        stage.run(ctx)

    def test_feature_key(self):
        from pipeline_newgen_rev1.runtime.stages.rewrite_plot_axis_to_sweep import RewritePlotAxisToSweepStage
        self.assertEqual(RewritePlotAxisToSweepStage().feature_key, "rewrite_plot_axis_to_sweep")


class TestPromptSweepDuplicateSelectorStage(unittest.TestCase):
    def test_feature_key(self):
        from pipeline_newgen_rev1.runtime.stages.prompt_sweep_duplicate_selector import PromptSweepDuplicateSelectorStage
        self.assertEqual(PromptSweepDuplicateSelectorStage().feature_key, "prompt_sweep_duplicate_selector")

    def test_skips_when_no_final_table(self):
        from unittest.mock import MagicMock
        from pipeline_newgen_rev1.runtime.stages.prompt_sweep_duplicate_selector import PromptSweepDuplicateSelectorStage

        ctx = MagicMock()
        ctx.final_table = None
        stage = PromptSweepDuplicateSelectorStage()
        stage.run(ctx)


class TestStageRegistryWithSweep(unittest.TestCase):
    def test_twentyone_stages_total(self):
        from pipeline_newgen_rev1.runtime.stages import STAGE_REGISTRY
        self.assertEqual(len(STAGE_REGISTRY), 21)

    def test_sweep_stages_in_registry(self):
        from pipeline_newgen_rev1.runtime.stages import STAGE_REGISTRY
        sweep_keys = [
            "parse_sweep_metadata",
            "apply_sweep_binning",
            "prompt_sweep_duplicate_selector",
            "rewrite_plot_axis_to_sweep",
        ]
        for key in sweep_keys:
            self.assertIn(key, STAGE_REGISTRY, f"{key} missing from STAGE_REGISTRY")

    def test_sweep_stages_in_processing_order(self):
        from pipeline_newgen_rev1.runtime.stages import PROCESSING_STAGE_ORDER
        self.assertIn("parse_sweep_metadata", PROCESSING_STAGE_ORDER)
        self.assertIn("apply_sweep_binning", PROCESSING_STAGE_ORDER)
        self.assertIn("prompt_sweep_duplicate_selector", PROCESSING_STAGE_ORDER)
        self.assertIn("rewrite_plot_axis_to_sweep", PROCESSING_STAGE_ORDER)

    def test_feature_flags_gate_sweep_in_load_mode(self):
        from pipeline_newgen_rev1.workflows.load_sweep.orchestrator import build_load_sweep_plan
        steps = build_load_sweep_plan("load")
        by_key = {s.feature_key: s for s in steps}
        self.assertFalse(by_key["parse_sweep_metadata"].enabled)
        self.assertFalse(by_key["apply_sweep_binning"].enabled)
        self.assertFalse(by_key["prompt_sweep_duplicate_selector"].enabled)
        self.assertFalse(by_key["rewrite_plot_axis_to_sweep"].enabled)

    def test_feature_flags_enable_sweep_in_sweep_mode(self):
        from pipeline_newgen_rev1.workflows.load_sweep.orchestrator import build_load_sweep_plan
        steps = build_load_sweep_plan("sweep")
        by_key = {s.feature_key: s for s in steps}
        self.assertTrue(by_key["parse_sweep_metadata"].enabled)
        self.assertTrue(by_key["apply_sweep_binning"].enabled)
        self.assertTrue(by_key["prompt_sweep_duplicate_selector"].enabled)
        self.assertTrue(by_key["rewrite_plot_axis_to_sweep"].enabled)


if __name__ == "__main__":
    unittest.main()
