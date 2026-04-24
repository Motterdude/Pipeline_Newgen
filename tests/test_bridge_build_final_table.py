"""Unit tests for ``BuildFinalTableBridgeStage`` using a mocked legacy module.

The real ``nanum_pipeline_29`` module is heavy (matplotlib, 9k+ lines) and may
not be importable in the dev env. These tests replace it in ``sys.modules``
with a stub so the bridge wiring can be exercised everywhere.
"""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.runtime.context import RuntimeContext


@dataclass
class _StubMeta:
    path: Path
    source_type: str


class _StubBundle:
    def __init__(self) -> None:
        self.defaults_cfg = {"RAW_INPUT_DIR": "", "OUT_DIR": ""}
        self.mappings = {"power_kw": {"mean": "Power_kW"}}
        self.instruments_df = pd.DataFrame({"key": ["a"]})
        self.reporting_df = pd.DataFrame({"col": ["b"]})


def _install_stub_legacy(module_name: str = "nanum_pipeline_29") -> MagicMock:
    """Install a stub legacy module in ``sys.modules`` and return a MagicMock
    that records calls for the functions the bridge uses."""
    module = types.ModuleType(module_name)
    tracker = MagicMock()

    def _parse_meta(path: Path) -> _StubMeta:
        suffix = path.suffix.lower()
        if suffix == ".xlsx":
            return _StubMeta(path=path, source_type="LABVIEW")
        name = path.name.lower()
        if name.endswith("_m.csv"):
            return _StubMeta(path=path, source_type="MOTEC")
        return _StubMeta(path=path, source_type="KIBOX")

    def _load_pipeline29_config_bundle(**_kwargs):
        tracker.load_pipeline29_config_bundle(**_kwargs)
        return _StubBundle()

    def _apply_runtime_path_overrides(defaults_cfg, config_bundle=None, **_kwargs):
        tracker.apply_runtime_path_overrides(defaults_cfg, config_bundle=config_bundle)

    def _read_labview_xlsx(meta):
        tracker.read_labview_xlsx(meta)
        return pd.DataFrame({"Power_kW": [50.0]})

    def _compute_trechos_stats(lv_raw, instruments_df):
        tracker.compute_trechos_stats(len(lv_raw), len(instruments_df))
        return pd.DataFrame({"Power_kW": [50.0], "Iteracao": [1]})

    def _compute_ponto_stats(trechos):
        tracker.compute_ponto_stats(len(trechos))
        return pd.DataFrame({"Power_kW": [50.0], "Iteracao": [1], "Sentido_Carga": ["sub"]})

    def _load_fuel_properties_lookup(bundle, defaults_cfg):
        tracker.load_fuel_properties_lookup()
        return pd.DataFrame({"Fuel_Label": ["E75H25"], "LHV_kJ_kg": [25000.0]})

    def _kibox_aggregate(kibox_metas):
        tracker.kibox_aggregate(len(kibox_metas))
        return pd.DataFrame({"kibox_col": [1.0]})

    def _read_motec_csv(meta):
        tracker.read_motec_csv(meta)
        return pd.DataFrame({"Lambda": [1.1]})

    def _compute_motec_trechos_stats(motec_raw):
        tracker.compute_motec_trechos_stats(len(motec_raw))
        return pd.DataFrame({"Lambda_mean": [1.1]})

    def _compute_motec_ponto_stats(motec_trechos):
        tracker.compute_motec_ponto_stats(len(motec_trechos))
        return pd.DataFrame({"Lambda_mean": [1.1]})

    def _build_final_table(ponto, fuel_properties, kibox_agg, motec_ponto, mappings, instruments_df, reporting_df, defaults_cfg):
        tracker.build_final_table(
            len(ponto), len(fuel_properties), len(kibox_agg), len(motec_ponto)
        )
        return pd.DataFrame({"Power_kW": [50.0], "Iteracao": [1], "BSFC_g_kWh": [250.0]})

    module.parse_meta = _parse_meta
    module.load_pipeline29_config_bundle = _load_pipeline29_config_bundle
    module.apply_runtime_path_overrides = _apply_runtime_path_overrides
    module.read_labview_xlsx = _read_labview_xlsx
    module.compute_trechos_stats = _compute_trechos_stats
    module.compute_ponto_stats = _compute_ponto_stats
    module.load_fuel_properties_lookup = _load_fuel_properties_lookup
    module.kibox_aggregate = _kibox_aggregate
    module.read_motec_csv = _read_motec_csv
    module.compute_motec_trechos_stats = _compute_motec_trechos_stats
    module.compute_motec_ponto_stats = _compute_motec_ponto_stats
    module.build_final_table = _build_final_table

    sys.modules[module_name] = module
    return tracker


def _remove_stub_legacy(module_name: str = "nanum_pipeline_29") -> None:
    sys.modules.pop(module_name, None)


class BuildFinalTableBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracker = _install_stub_legacy()

    def tearDown(self) -> None:
        _remove_stub_legacy()

    def _ctx_with_input(self, input_dir: Path) -> RuntimeContext:
        ctx = RuntimeContext(project_root=input_dir)
        ctx.input_dir = input_dir
        return ctx

    def test_populates_final_table_via_legacy_chain(self) -> None:
        from pipeline_newgen_rev1.bridges.legacy_runtime import BuildFinalTableBridgeStage

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)
            (raw / "50KW_E75H25.xlsx").write_bytes(b"")  # discovered but read is stubbed
            (raw / "50KW_D85B15_i.csv").write_bytes(b"")  # KIBOX
            (raw / "50KW_D85B15_m.csv").write_bytes(b"")  # MOTEC

            ctx = self._ctx_with_input(raw)
            BuildFinalTableBridgeStage().run(ctx)

            self.assertIsNotNone(ctx.final_table)
            assert ctx.final_table is not None  # narrow
            self.assertEqual(list(ctx.final_table.columns), ["Power_kW", "Iteracao", "BSFC_g_kWh"])
            self.assertIsNotNone(ctx.ponto)
            self.assertIsNotNone(ctx.fuel_properties)
            self.assertIsNotNone(ctx.kibox_agg)
            self.assertIsNotNone(ctx.motec_ponto)

            # Verify the chain was invoked in the expected order on the tracker.
            # Note: legacy globals (RAW_DIR, PROCESS_DIR, OUT_DIR, PLOTS_DIR)
            # are set directly on the module object by the bridge instead of
            # via apply_runtime_path_overrides (which is interactive).
            method_calls = [c[0] for c in self.tracker.mock_calls]
            self.assertIn("load_pipeline29_config_bundle", method_calls)
            self.assertIn("read_labview_xlsx", method_calls)
            self.assertIn("compute_trechos_stats", method_calls)
            self.assertIn("compute_ponto_stats", method_calls)
            self.assertIn("load_fuel_properties_lookup", method_calls)
            self.assertIn("kibox_aggregate", method_calls)
            self.assertIn("read_motec_csv", method_calls)
            self.assertIn("compute_motec_trechos_stats", method_calls)
            self.assertIn("compute_motec_ponto_stats", method_calls)
            self.assertIn("build_final_table", method_calls)

    def test_skips_when_input_dir_missing(self) -> None:
        from pipeline_newgen_rev1.bridges.legacy_runtime import BuildFinalTableBridgeStage

        ctx = RuntimeContext(project_root=Path("."))
        # input_dir stays None
        BuildFinalTableBridgeStage().run(ctx)
        self.assertIsNone(ctx.final_table)
        self.assertIsNone(ctx.ponto)

    def test_motec_empty_when_no_motec_files(self) -> None:
        from pipeline_newgen_rev1.bridges.legacy_runtime import BuildFinalTableBridgeStage

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)
            (raw / "50KW.xlsx").write_bytes(b"")
            # no *_m.csv file

            ctx = self._ctx_with_input(raw)
            BuildFinalTableBridgeStage().run(ctx)

            self.assertIsNotNone(ctx.motec_ponto)
            assert ctx.motec_ponto is not None
            self.assertTrue(ctx.motec_ponto.empty)

            method_calls = [c[0] for c in self.tracker.mock_calls]
            self.assertNotIn("read_motec_csv", method_calls)
            self.assertNotIn("compute_motec_ponto_stats", method_calls)


if __name__ == "__main__":
    unittest.main()
