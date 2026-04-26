"""Unit tests for ``RunCompareIteracoesBridgeStage`` using a mocked legacy module."""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.runtime.context import RuntimeContext


class _StubBundle:
    def __init__(self) -> None:
        self.compare_df = pd.DataFrame({
            "enabled": ["1"],
            "left_series": ["baseline_media"],
            "right_series": ["aditivado_media"],
            "metric_id": ["consumo"],
            "with_uncertainty": ["1"],
            "without_uncertainty": ["0"],
            "show_uncertainty": ["on"],
            "notes": ["stub"],
        })
        self.mappings = {"power_kw": {"mean": "Power_kW"}}


def _install_stub_legacy(*, raise_in_compare: bool = False, write_png: bool = True) -> MagicMock:
    module = types.ModuleType("nanum_pipeline_29")
    tracker = MagicMock()

    def _load_pipeline29_config_bundle(**_kwargs):
        tracker.load_pipeline29_config_bundle(**_kwargs)
        return _StubBundle()

    def _default_compare_iter_pairs():
        tracker._default_compare_iter_pairs()
        return [("baseline_media", "aditivado_media")]

    def _resolve_compare_iter_requests(compare_df, *, fallback_pairs=None, force_fallback_pairs=False):
        tracker._resolve_compare_iter_requests(
            compare_df_rows=len(compare_df) if compare_df is not None else 0,
        )
        return [{"left_id": "baseline_media", "right_id": "aditivado_media", "metric_id": "consumo"}], "stub"

    def _plot_compare_iteracoes_bl_vs_adtv(df, *, root_plot_dir=None, mappings=None, compare_iter_pairs=None, compare_requests=None):
        tracker._plot_compare_iteracoes_bl_vs_adtv(
            df_rows=len(df), root_plot_dir=str(root_plot_dir),
        )
        if raise_in_compare:
            raise RuntimeError("synthetic compare failure")
        if write_png and root_plot_dir is not None:
            target = Path(root_plot_dir) / "compare_iteracoes_bl_vs_adtv"
            target.mkdir(parents=True, exist_ok=True)
            (target / "stub_absolute.png").write_bytes(b"\x89PNG_stub")
            (target / "stub_delta_pct.png").write_bytes(b"\x89PNG_stub")
            xlsx_path = target / "compare_iteracoes_metricas_incertezas.xlsx"
            pd.DataFrame({"metric": ["consumo"], "delta_pct": [0.5]}).to_excel(xlsx_path, index=False)

    module.load_pipeline29_config_bundle = _load_pipeline29_config_bundle
    module._default_compare_iter_pairs = _default_compare_iter_pairs
    module._resolve_compare_iter_requests = _resolve_compare_iter_requests
    module._plot_compare_iteracoes_bl_vs_adtv = _plot_compare_iteracoes_bl_vs_adtv

    sys.modules["nanum_pipeline_29"] = module
    return tracker


def _remove_stub_legacy() -> None:
    sys.modules.pop("nanum_pipeline_29", None)


class RunCompareIteracoesBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracker = _install_stub_legacy()

    def tearDown(self) -> None:
        _remove_stub_legacy()

    def test_skips_when_final_table_is_none(self) -> None:
        from pipeline_newgen_rev1.bridges.legacy_runtime import RunCompareIteracoesBridgeStage

        with tempfile.TemporaryDirectory() as tmp:
            ctx = RuntimeContext(project_root=Path(tmp))
            ctx.output_dir = Path(tmp)
            RunCompareIteracoesBridgeStage().run(ctx)
            self.assertIsNone(ctx.compare_iteracoes_export_path)
            self.assertFalse((Path(tmp) / "plots" / "compare_iteracoes_bl_vs_adtv").exists())

    def test_invokes_legacy_compare_and_stores_path(self) -> None:
        from pipeline_newgen_rev1.bridges.legacy_runtime import RunCompareIteracoesBridgeStage

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            ctx = RuntimeContext(project_root=out)
            ctx.output_dir = out
            ctx.final_table = pd.DataFrame({"Load_kW": [10.0], "Consumo_kg_h": [2.0]})

            RunCompareIteracoesBridgeStage().run(ctx)

            self.assertIsNotNone(ctx.compare_iteracoes_export_path)
            self.assertTrue(ctx.compare_iteracoes_export_path.exists())
            self.assertTrue(ctx.compare_iteracoes_export_path.name.endswith(".xlsx"))

            target_dir = out / "plots" / "compare_iteracoes_bl_vs_adtv"
            self.assertTrue(target_dir.exists())
            pngs = list(target_dir.glob("*.png"))
            self.assertEqual(len(pngs), 2)

            method_calls = [c[0] for c in self.tracker.mock_calls]
            self.assertIn("load_pipeline29_config_bundle", method_calls)
            self.assertIn("_resolve_compare_iter_requests", method_calls)
            self.assertIn("_plot_compare_iteracoes_bl_vs_adtv", method_calls)

    def test_catches_legacy_exception_gracefully(self) -> None:
        _remove_stub_legacy()
        self.tracker = _install_stub_legacy(raise_in_compare=True)

        from pipeline_newgen_rev1.bridges.legacy_runtime import RunCompareIteracoesBridgeStage

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            ctx = RuntimeContext(project_root=out)
            ctx.output_dir = out
            ctx.final_table = pd.DataFrame({"Load_kW": [10.0]})

            RunCompareIteracoesBridgeStage().run(ctx)
            self.assertIsNone(ctx.compare_iteracoes_export_path)


if __name__ == "__main__":
    unittest.main()
