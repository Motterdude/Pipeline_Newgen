"""Tests for the native upstream-frames preparation: fuel properties, KiBox
cross-file aggregation, and MoTeC trechos/ponto.
"""
from __future__ import annotations

import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pipeline_newgen_rev1.config.adapter import DEFAULT_FUEL_PROPERTY_COLUMNS
from pipeline_newgen_rev1.runtime.fuel_properties import (
    load_fuel_properties,
    _fuel_label_from_components,
    _normalize_fuel_properties_df,
)
from pipeline_newgen_rev1.runtime.motec_stats import (
    compute_motec_ponto_stats,
    compute_motec_trechos_stats,
)
from pipeline_newgen_rev1.runtime.stages.prepare_upstream_frames import (
    PrepareUpstreamFramesStage,
    _aggregate_kibox_cross_file,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _fuel_row(label="E75H25", dies=0.0, biod=0.0, etoh=75.0, h2o=25.0, lhv=27600.0,
              density=None, cost=None):
    return {
        "Fuel_Label": label, "DIES_pct": dies, "BIOD_pct": biod,
        "EtOH_pct": etoh, "H2O_pct": h2o, "LHV_kJ_kg": lhv,
        "Fuel_Density_kg_m3": density, "Fuel_Cost_R_L": cost,
        "reference": None, "notes": None,
    }


def _make_motec_raw(n_samples=30, n_windows=2):
    rows = []
    for w in range(n_windows):
        for i in range(n_samples):
            rows.append({
                "BaseName": "file1",
                "Load_kW": 50.0,
                "DIES_pct": 0.0,
                "BIOD_pct": 0.0,
                "EtOH_pct": 75.0,
                "H2O_pct": 25.0,
                "WindowID": w,
                "Index": i,
                "Lambda": 1.0 + w * 0.05,
                "RPM": 3000.0 + w * 50,
            })
    return pd.DataFrame(rows)


def _make_kibox_aggregate_rows(n_files=2):
    rows = []
    for i in range(n_files):
        rows.append({
            "aggregate_row": {
                "SourceFolder": "subindo_aditivado_1",
                "Load_kW": 50.0,
                "DIES_pct": 0.0,
                "BIOD_pct": 0.0,
                "EtOH_pct": 75.0,
                "H2O_pct": 25.0,
                "KIBOX_Pmax_bar": 40.0 + i * 2.0,
                "KIBOX_IMEPn_bar": 8.0 + i * 0.5,
                "KIBOX_N_files": 1,
            }
        })
    return rows


# --------------------------------------------------------------------------- #
# Fuel properties
# --------------------------------------------------------------------------- #

class TestLoadFuelProperties(unittest.TestCase):
    def test_from_config_only(self):
        fuel_rows = [_fuel_row()]
        result = load_fuel_properties(fuel_rows, defaults={})
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(float(result.iloc[0]["LHV_kJ_kg"]), 27600.0)

    def test_empty_config_no_csv(self):
        result = load_fuel_properties([], defaults={})
        self.assertEqual(len(result), 0)
        for c in DEFAULT_FUEL_PROPERTY_COLUMNS:
            self.assertIn(c, result.columns)

    def test_fills_defaults(self):
        fuel_rows = [_fuel_row(density=None, cost=None)]
        defaults = {
            "fuel_density_kg_m3_e75h25": "789.5",
            "fuel_cost_r_l_e75h25": "3.50",
        }
        result = load_fuel_properties(fuel_rows, defaults=defaults)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(float(result.iloc[0]["Fuel_Density_kg_m3"]), 789.5)
        self.assertAlmostEqual(float(result.iloc[0]["Fuel_Cost_R_L"]), 3.50)

    def test_label_inferred(self):
        row = _fuel_row(label=None, etoh=75.0, h2o=25.0)
        result = load_fuel_properties([row], defaults={})
        self.assertEqual(result.iloc[0]["Fuel_Label"], "E75H25")

    def test_with_lhv_csv_fallback(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
            f.write("DIES_pct,BIOD_pct,EtOH_pct,H2O_pct,LHV_kJ_kg\n")
            f.write("85,15,0,0,42500\n")
            csv_path = Path(f.name)
        try:
            result = load_fuel_properties([], defaults={}, lhv_csv_path=csv_path)
            self.assertGreater(len(result), 0)
            self.assertAlmostEqual(float(result.iloc[0]["LHV_kJ_kg"]), 42500.0)
        finally:
            csv_path.unlink(missing_ok=True)


class TestFuelLabelFromComponents(unittest.TestCase):
    def test_e75h25(self):
        self.assertEqual(_fuel_label_from_components(0, 0, 75, 25), "E75H25")

    def test_d85b15(self):
        self.assertEqual(_fuel_label_from_components(85, 15, 0, 0), "D85B15")

    def test_empty(self):
        self.assertEqual(_fuel_label_from_components(None, None, None, None), "")


# --------------------------------------------------------------------------- #
# KiBox aggregation
# --------------------------------------------------------------------------- #

class TestKiboxCrossFileAggregation(unittest.TestCase):
    def test_single_file(self):
        rows = _make_kibox_aggregate_rows(n_files=1)
        result = _aggregate_kibox_cross_file(rows)
        self.assertEqual(len(result), 1)
        self.assertIn("KIBOX_Pmax_bar", result.columns)

    def test_two_files_same_group(self):
        rows = _make_kibox_aggregate_rows(n_files=2)
        result = _aggregate_kibox_cross_file(rows)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(float(result.iloc[0]["KIBOX_Pmax_bar"]), 41.0)
        self.assertAlmostEqual(float(result.iloc[0]["KIBOX_IMEPn_bar"]), 8.25)
        self.assertEqual(float(result.iloc[0]["KIBOX_N_files"]), 2.0)

    def test_empty(self):
        result = _aggregate_kibox_cross_file([])
        self.assertEqual(len(result), 0)


# --------------------------------------------------------------------------- #
# MoTeC trechos/ponto
# --------------------------------------------------------------------------- #

class TestMotecTrechosStats(unittest.TestCase):
    def test_basic(self):
        raw = _make_motec_raw(n_samples=30, n_windows=2)
        result = compute_motec_trechos_stats(raw)
        self.assertEqual(len(result), 2)
        self.assertIn("Lambda_mean", result.columns)
        self.assertIn("Motec_N_samples", result.columns)
        self.assertTrue((result["Motec_N_samples"] == 30).all())

    def test_filters_small(self):
        raw = _make_motec_raw(n_samples=29, n_windows=1)
        result = compute_motec_trechos_stats(raw)
        self.assertEqual(len(result), 0)

    def test_empty(self):
        result = compute_motec_trechos_stats(pd.DataFrame())
        self.assertEqual(len(result), 0)


class TestMotecPontoStats(unittest.TestCase):
    def test_aggregation(self):
        raw = _make_motec_raw(n_samples=30, n_windows=2)
        trechos = compute_motec_trechos_stats(raw)
        ponto = compute_motec_ponto_stats(trechos)
        self.assertEqual(len(ponto), 1)
        self.assertIn("Motec_N_trechos_validos", ponto.columns)
        self.assertIn("Motec_N_files", ponto.columns)
        self.assertEqual(int(ponto.iloc[0]["Motec_N_trechos_validos"]), 2)

    def test_empty(self):
        result = compute_motec_ponto_stats(pd.DataFrame())
        self.assertEqual(len(result), 0)

    def test_suffix_normalization(self):
        raw = _make_motec_raw(n_samples=30, n_windows=2)
        trechos = compute_motec_trechos_stats(raw)
        ponto = compute_motec_ponto_stats(trechos)
        for col in ponto.columns:
            self.assertNotIn("_mean_mean_of_windows", col)


# --------------------------------------------------------------------------- #
# Stage integration
# --------------------------------------------------------------------------- #

class TestPrepareUpstreamFramesStage(unittest.TestCase):
    def test_feature_key(self):
        stage = PrepareUpstreamFramesStage()
        self.assertEqual(stage.feature_key, "prepare_upstream_frames")

    def test_populates_fuel(self):
        ctx = MagicMock()
        ctx.bundle = MagicMock()
        ctx.bundle.fuel_properties = [_fuel_row()]
        ctx.bundle.defaults = {}
        ctx.bundle.text_dir = None
        ctx.kibox_aggregate_rows = []
        ctx.motec_frames = []
        ctx.fuel_properties = None
        ctx.kibox_agg = None
        ctx.motec_ponto = None

        stage = PrepareUpstreamFramesStage()
        stage.run(ctx)
        self.assertIsInstance(ctx.fuel_properties, pd.DataFrame)
        self.assertGreater(len(ctx.fuel_properties), 0)

    def test_populates_kibox(self):
        ctx = MagicMock()
        ctx.bundle = MagicMock()
        ctx.bundle.fuel_properties = [_fuel_row()]
        ctx.bundle.defaults = {}
        ctx.bundle.text_dir = None
        ctx.kibox_aggregate_rows = _make_kibox_aggregate_rows(2)
        ctx.motec_frames = []
        ctx.fuel_properties = None
        ctx.kibox_agg = None
        ctx.motec_ponto = None

        stage = PrepareUpstreamFramesStage()
        stage.run(ctx)
        self.assertIsInstance(ctx.kibox_agg, pd.DataFrame)
        self.assertGreater(len(ctx.kibox_agg), 0)

    def test_populates_motec(self):
        ctx = MagicMock()
        ctx.bundle = MagicMock()
        ctx.bundle.fuel_properties = [_fuel_row()]
        ctx.bundle.defaults = {}
        ctx.bundle.text_dir = None
        ctx.kibox_aggregate_rows = []
        ctx.motec_frames = [_make_motec_raw(n_samples=30, n_windows=2)]
        ctx.fuel_properties = None
        ctx.kibox_agg = None
        ctx.motec_ponto = None

        stage = PrepareUpstreamFramesStage()
        stage.run(ctx)
        self.assertIsInstance(ctx.motec_ponto, pd.DataFrame)
        self.assertGreater(len(ctx.motec_ponto), 0)

    def test_skips_gracefully(self):
        ctx = MagicMock()
        ctx.bundle = None
        ctx.kibox_aggregate_rows = []
        ctx.motec_frames = []
        ctx.fuel_properties = None
        ctx.kibox_agg = None
        ctx.motec_ponto = None

        stage = PrepareUpstreamFramesStage()
        stage.run(ctx)
        self.assertIsNone(ctx.fuel_properties)


if __name__ == "__main__":
    unittest.main()
