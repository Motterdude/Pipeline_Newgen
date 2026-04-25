"""Tests for plot_scope gating in the runner."""
from __future__ import annotations

import unittest

from _path import ROOT  # noqa: F401

from pipeline_newgen_rev1.runtime.runner import _PLOT_SCOPE_INCLUDE


class TestPlotScopeInclude(unittest.TestCase):
    def test_all_is_none(self) -> None:
        self.assertIsNone(_PLOT_SCOPE_INCLUDE["all"])

    def test_none_is_empty_set(self) -> None:
        self.assertEqual(_PLOT_SCOPE_INCLUDE["none"], set())

    def test_unitary_includes_unitary_and_time(self) -> None:
        s = _PLOT_SCOPE_INCLUDE["unitary"]
        self.assertIn("run_unitary_plots", s)
        self.assertIn("plot_time_diagnostics", s)
        self.assertNotIn("run_compare_plots", s)
        self.assertNotIn("plot_compare_iteracoes", s)
        self.assertNotIn("run_special_load_plots", s)

    def test_compare_includes_compare_and_time(self) -> None:
        s = _PLOT_SCOPE_INCLUDE["compare"]
        self.assertIn("run_compare_plots", s)
        self.assertIn("plot_compare_iteracoes", s)
        self.assertIn("plot_time_diagnostics", s)
        self.assertNotIn("run_unitary_plots", s)
        self.assertNotIn("run_special_load_plots", s)

    def test_all_four_scopes_present(self) -> None:
        self.assertEqual(set(_PLOT_SCOPE_INCLUDE.keys()), {"all", "unitary", "compare", "none"})


class TestPlotScopeContext(unittest.TestCase):
    def test_context_has_plot_scope_field(self) -> None:
        from pipeline_newgen_rev1.runtime.context import RuntimeContext
        from pathlib import Path
        ctx = RuntimeContext(project_root=Path("."))
        self.assertEqual(ctx.plot_scope, "all")

    def test_context_has_compare_iter_pairs_override(self) -> None:
        from pipeline_newgen_rev1.runtime.context import RuntimeContext
        from pathlib import Path
        ctx = RuntimeContext(project_root=Path("."))
        self.assertIsNone(ctx.compare_iter_pairs_override)


if __name__ == "__main__":
    unittest.main()
