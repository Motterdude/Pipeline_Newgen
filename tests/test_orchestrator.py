from __future__ import annotations

import unittest

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.workflows.load_sweep.orchestrator import build_load_sweep_plan, summarize_plan


class OrchestratorTests(unittest.TestCase):
    def test_load_plan_marks_sweep_steps_disabled(self) -> None:
        steps = build_load_sweep_plan("load")
        by_key = {step.feature_key: step for step in steps}
        self.assertFalse(by_key["apply_sweep_binning"].enabled)
        self.assertFalse(by_key["prompt_sweep_duplicate_selector"].enabled)
        self.assertTrue(by_key["run_compare_plots"].enabled)
        self.assertTrue(by_key["run_special_load_plots"].enabled)

    def test_sweep_plan_disables_compare_steps_by_default(self) -> None:
        steps = build_load_sweep_plan("sweep")
        by_key = {step.feature_key: step for step in steps}
        self.assertTrue(by_key["apply_sweep_binning"].enabled)
        self.assertTrue(by_key["rewrite_plot_axis_to_sweep"].enabled)
        self.assertFalse(by_key["run_compare_plots"].enabled)
        self.assertFalse(by_key["compute_compare_iteracoes"].enabled)
        self.assertFalse(by_key["plot_compare_iteracoes"].enabled)
        self.assertFalse(by_key["run_special_load_plots"].enabled)

    def test_summary_counts_enabled_and_disabled_steps(self) -> None:
        summary = summarize_plan(build_load_sweep_plan("load"))
        self.assertEqual(summary["total_steps"], 22)
        self.assertGreater(summary["enabled_steps"], 0)
        self.assertGreater(summary["disabled_steps"], 0)
        self.assertIn("plotting", summary["enabled_stage_counts"])


if __name__ == "__main__":
    unittest.main()

